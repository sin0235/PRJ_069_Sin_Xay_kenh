"""Kiểm tra quyền theo tác vụ, toàn vẹn tệp và phục hồi worker từ xa."""
import hashlib
import pytest
from src.modules.tac_vu_tu_xa.service import TaskStore, RemoteTaskError


def test_worker_only_reads_declared_input_and_stale_attempt_cannot_finish(tmp_path):
    store = TaskStore(tmp_path / 'jobs.sqlite3', tmp_path / 'scratch')
    source = tmp_path / 'source.mp4'
    source.write_bytes(b'nguon-goc')
    task = store.create('TRANSCRIBE', {'mode': 'words'}, [source], 'ws1', 'AUTO_EDIT')
    claimed, token = store.claim('run-1')
    assert claimed['id'] == task
    assert 'path' not in claimed['inputs'][0]
    assert store.input_path(task, token, 0) == source
    with pytest.raises(RemoteTaskError):
        store.input_path(task, 'sai-token', 0)
    with pytest.raises(RemoteTaskError):
        store.input_path(task, token, 1)
    store.cancel(task)
    with pytest.raises(RemoteTaskError):
        store.complete(task, token, {'words': []}, None)


def test_chunk_resume_hash_and_completion_are_idempotent(tmp_path):
    store = TaskStore(tmp_path / 'jobs.sqlite3', tmp_path / 'scratch')
    task = store.create('EXTRACT_AUDIO', {}, [], 'ws1', 'AUTO_EDIT')
    _, token = store.claim('run-1')
    assert store.append(task, token, 0, b'abc') == 3
    assert store.append(task, token, 0, b'abc') == 3
    with pytest.raises(RemoteTaskError):
        store.append(task, token, 1, b'xx')
    digest = hashlib.sha256(b'abc').hexdigest()
    with pytest.raises(RemoteTaskError):
        store.complete(task, token, {}, {'size': 3, 'sha256': '0' * 64})
    store.complete(task, token, {'ok': True}, {'size': 3, 'sha256': digest})
    store.complete(task, token, {'ok': True}, {'size': 3, 'sha256': digest})
    assert store.get(task)['state'] == 'SUCCEEDED'
    with pytest.raises(RemoteTaskError):
        store.complete(task, token, {}, {'size': 3, 'sha256': digest})


def test_expired_lease_fences_worker_and_queue_survives_restart(tmp_path):
    store = TaskStore(tmp_path / 'jobs.sqlite3', tmp_path / 'scratch')
    task = store.create('QC', {}, [], 'ws1', 'AI_VIDEO')
    _, token = store.claim('run-1')
    with store.connect() as db:
        db.execute('UPDATE tasks SET lease_until=0 WHERE id=?', (task,))
    restored = TaskStore(tmp_path / 'jobs.sqlite3', tmp_path / 'scratch')
    with pytest.raises(RemoteTaskError):
        restored.heartbeat(task, token)
    assert restored.claim('run-2') is None
    assert restored.get(task)['state'] == 'LOST'


def test_oidc_checks_signature_repo_id_ref_event_and_audience(monkeypatch):
    import base64
    import json
    import time
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.primitives import hashes
    from src.modules.tac_vu_tu_xa import identity
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(identity, 'public_keys', lambda: {'test': private.public_key()})
    for name, value in {'REMOTE_GITHUB_REPOSITORY': 'owner/repo', 'REMOTE_GITHUB_REPOSITORY_ID': '123',
                        'REMOTE_GITHUB_REF': 'dev', 'REMOTE_PUBLIC_ORIGIN': 'https://test.example'}.items():
        monkeypatch.setenv(name, value)
    claims = {'iss': identity.ISSUER, 'aud': 'https://test.example', 'repository': 'owner/repo',
              'repository_id': '123', 'ref': 'refs/heads/dev', 'event_name': 'workflow_dispatch',
              'workflow_ref': 'owner/repo/.github/workflows/kiem_thu_video_tu_xa.yaml@refs/heads/dev',
              'exp': time.time() + 300, 'nbf': time.time() - 10, 'iat': time.time(), 'sub': 'trusted', 'run_id': '42'}
    def sign(payload):
        enc = lambda value: base64.urlsafe_b64encode(value).rstrip(b'=').decode()
        message = enc(json.dumps({'alg': 'RS256', 'kid': 'test'}).encode()) + '.' + enc(json.dumps(payload).encode())
        return message + '.' + enc(private.sign(message.encode(), padding.PKCS1v15(), hashes.SHA256()))
    assert identity.verify_oidc(sign(claims))['run_id'] == '42'
    for name, wrong in [('aud', 'https://evil.example'), ('repository_id', '456'), ('ref', 'refs/heads/main'),
                        ('event_name', 'pull_request'), ('exp', time.time() - 1)]:
        with pytest.raises(RemoteTaskError):
            identity.verify_oidc(sign({**claims, name: wrong}))
    with pytest.raises(RemoteTaskError):
        identity.verify_oidc(sign(claims)[:-3] + 'xxx')


def test_offload_never_calls_local_engine_and_resets_scope(monkeypatch, tmp_path):
    from src.modules.tac_vu_tu_xa import client
    monkeypatch.setenv('REMOTE_COMPUTE_MODE', 'github')
    monkeypatch.delenv('REMOTE_ENGINE_CHILD', raising=False)
    source = tmp_path / 'source.wav'
    source.write_bytes(b'not-read-by-engine')
    calls = []
    def execute(stage, operation, arguments, inputs, output=None):
        calls.append((stage, operation, arguments, inputs, client.scope.get()))
        return [{'text': 'lời thật'}]
    monkeypatch.setattr(client, 'execute', execute)
    @client.offload('transcribe_words', 'TRANSCRIBE')
    def engine(audio_path):
        pytest.fail('Đã gọi model trên local')
    @client.pipeline('AUTO_EDIT')
    def pipeline(workspace_id, job_id=None):
        return engine(source)
    assert pipeline('ws1') == [{'text': 'lời thật'}]
    assert calls[0][2] == {'audio_path': {'remote_input': 0}}
    assert calls[0][3] == [source]
    assert calls[0][4]['workspace'] == 'ws1'
    assert client.scope.get() is None


def test_remote_mode_blocks_unwrapped_local_ffmpeg(monkeypatch):
    from src.media_process import run_media_command
    monkeypatch.setenv('REMOTE_COMPUTE_MODE', 'github')
    monkeypatch.delenv('REMOTE_ENGINE_CHILD', raising=False)
    with pytest.raises(RuntimeError, match='REMOTE_UNWRAPPED_MEDIA_COMMAND'):
        run_media_command(['ffmpeg', '-version'])


def test_input_range_and_result_reject_wrong_token(monkeypatch, tmp_path):
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from fastapi.testclient import TestClient
    from src.modules.tac_vu_tu_xa import router as module
    store = TaskStore(tmp_path / 'jobs.sqlite3', tmp_path / 'scratch')
    source = tmp_path / 'source.mp4'
    source.write_bytes(b'0123456789')
    task = store.create('QC', {}, [source], 'ws1', 'AUTO_EDIT')
    _, token = store.claim('run-1')
    monkeypatch.setattr(module, 'get_store', lambda: store)
    app = FastAPI()
    app.include_router(module.router)
    @app.exception_handler(RemoteTaskError)
    async def rejected(request: Request, exc: RemoteTaskError):
        return JSONResponse({'error': str(exc)}, status_code=403)
    with TestClient(app) as client:
        url = f'/v1/remote-tasks/{task}/inputs/0'
        response = client.get(url, headers={'Authorization': 'Bearer ' + token, 'Range': 'bytes=2-5'})
        assert response.status_code == 206
        assert response.content == b'2345'
        assert response.headers['content-range'] == 'bytes 2-5/10'
        assert client.get(url, headers={'Authorization': 'Bearer wrong'}).status_code == 403
        assert client.post(f'/v1/remote-tasks/{task}/complete', headers={'Authorization': 'Bearer wrong'},
                           json={'result': {}}).status_code == 403


def test_scene_model_roundtrip_uses_existing_schema():
    from src.modules.tac_vu_tu_xa.stages import decode_arguments
    from src.modules.tao_video_noi_dung.planner import UiScene
    scene = UiScene(layout='CHAT', highlight='Kiểm tra', messages=[
        {'role': 'customer', 'text': 'Hỏi', 'at_s': 0},
        {'role': 'ai', 'text': 'Trả lời', 'at_s': 1},
    ])
    restored = decode_arguments({'remote_model': 'UiScene', 'value': scene.model_dump(mode='json')}, [])
    assert isinstance(restored, UiScene)
    assert restored.highlight == scene.highlight


def test_dev_queue_does_not_claim_or_update_imported_jobs(monkeypatch):
    from sqlalchemy import create_engine, text, select, update
    from sqlalchemy.orm import Session
    from src.models.entities import AIGenerationJob
    from src.modules.tac_vu_tu_xa.queue_scope import restrict_dev_queue
    monkeypatch.setenv('REMOTE_COMPUTE_MODE', 'github')
    monkeypatch.setenv('LOCAL_DEV_JOB_CUTOFF_UTC', '2026-11-03T00:00:00+00:00')
    engine = create_engine('sqlite://')
    table = AIGenerationJob.__tablename__
    with engine.begin() as conn:
        conn.execute(text(f'CREATE TABLE {table} (id TEXT PRIMARY KEY,created_at DATETIME,state TEXT)'))
        conn.execute(text(f"INSERT INTO {table} VALUES('old','2026-11-02 00:00:00','QUEUED'),('new','2026-11-04 00:00:00','QUEUED')"))
    with Session(engine) as session:
        restrict_dev_queue(session)
        assert session.execute(select(AIGenerationJob.id)).scalars().all() == ['new']
        session.execute(update(AIGenerationJob).values(state='RUNNING'))
        session.commit()
    with engine.connect() as conn:
        assert dict(conn.execute(text(f'SELECT id,state FROM {table}')).all()) == {'old': 'QUEUED', 'new': 'RUNNING'}
