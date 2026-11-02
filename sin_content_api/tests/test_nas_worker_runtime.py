from datetime import datetime, timedelta, timezone
import json
import sys
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.database import Base
from src.models.entities import AIGenerationJob, ContentVideoWorkerLease, Workspace
from src.modules.voice_studio import worker


def test_claim_voice_job_only_recovers_expired_leases():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    with Session(engine) as db:
        db.add(Workspace(id='ws-runtime', name='Runtime', slug='runtime'))
        def job(name, **fields):
            return AIGenerationJob(id=name, workspace_id='ws-runtime', asset_type='AUDIO',
                provider='VOICE_STUDIO', provider_mode='VIE_NEU_V3_TURBO', model_id='vieneu',
                idempotency_key=name, created_by='owner', request_payload_json='{}', **fields)
        db.add_all([
            ContentVideoWorkerLease(name=worker.LEASE_NAME, token='new-owner', expires_at=now + timedelta(minutes=8)),
            job('healthy', state='RUNNING', lease_token='healthy-owner', lease_expires_at=now + timedelta(minutes=5)),
            job('expired', state='RUNNING', lease_token='dead-owner', lease_expires_at=now - timedelta(minutes=1)),
        ])
        db.commit()
        claimed = worker.claim_next_voice_job(db, 'new-owner')
        assert claimed.id == 'expired'
        assert claimed.lease_token == 'new-owner'
        assert claimed.retry_count == 1
        db.expire_all()
        assert db.get(AIGenerationJob, 'healthy').lease_token == 'healthy-owner'
        assert db.get(AIGenerationJob, 'healthy').state == 'RUNNING'


def test_stale_voice_worker_cannot_infer_or_overwrite(monkeypatch):
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Workspace(id='ws-stale', name='Runtime', slug='stale'))
        db.add(AIGenerationJob(id='stale', workspace_id='ws-stale', asset_type='AUDIO',
            provider='VOICE_STUDIO', provider_mode='VIE_NEU_V3_TURBO', model_id='vieneu',
            idempotency_key='stale', created_by='owner', state='RUNNING',
            lease_token='new-owner', request_payload_json=json.dumps({'text':'Xin chào'})))
        db.commit()
    monkeypatch.setattr(worker, 'SessionLocal', lambda: Session(engine))
    monkeypatch.setattr(worker._LeaseHeartbeat, 'start', lambda self: None)
    monkeypatch.setattr(worker._LeaseHeartbeat, 'stop', lambda self: None)
    monkeypatch.setattr(worker.tts_provider_manager, 'synthesize', lambda *args: pytest.fail('stale worker inferred'))
    worker.process_voice_studio_job('stale', 'old-owner')
    with Session(engine) as db:
        job = db.get(AIGenerationJob, 'stale')
        assert job.state == 'RUNNING'
        assert job.lease_token == 'new-owner'


def test_media_command_timeout_is_bounded():
    from src.media_process import run_media_command
    import subprocess
    with pytest.raises(subprocess.TimeoutExpired):
        run_media_command([sys.executable, '-c', 'import time; time.sleep(20)'], timeout=0.05)


def test_production_tts_requires_prepared_model(monkeypatch, tmp_path):
    from src.model_runtime import synthesize_isolated
    from src.modules.tao_video_noi_dung.tts_provider import TTSProviderError
    monkeypatch.setenv('PRJ069_VIENU_HF_HOME', str(tmp_path))
    with pytest.raises(TTSProviderError, match='TTS_MODEL_NOT_READY'):
        synthesize_isolated({'provider':'VIE_NEU_V3_TURBO'}, 'Xin chào')


def test_production_gwen_explicitly_unavailable(monkeypatch):
    from src.model_runtime import require_provider
    from src.modules.tao_video_noi_dung.tts_provider import TTSProviderError
    monkeypatch.setenv('APP_ENV', 'production')
    with pytest.raises(TTSProviderError, match='TTS_PROVIDER_NOT_READY'):
        require_provider('GWEN_TTS')


def test_lost_global_lease_blocks_content_commit():
    from src.worker_fencing import fence_session, WorkerLeaseLost
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(ContentVideoWorkerLease(name=worker.LEASE_NAME, token='other',
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5)))
        db.commit()
        fence_session(db, 'dead-worker')
        db.add(Workspace(id='lost', name='Should not persist', slug='lost'))
        with pytest.raises(WorkerLeaseLost):
            db.commit()
        db.rollback()
    with Session(engine) as db:
        assert db.get(Workspace, 'lost') is None


def test_ready_model_detects_tampering(monkeypatch, tmp_path):
    import hashlib
    from src.model_runtime import model_status, MODEL_REVISIONS
    monkeypatch.setenv('PRJ069_VIENU_HF_HOME', str(tmp_path))
    (tmp_path / 'graph').write_bytes(b'good')
    (tmp_path / 'nas-model.json').write_text(json.dumps({'warmup': 'SUCCEEDED', 'revisions': MODEL_REVISIONS,
        'files':[{'path':'graph', 'size':4, 'sha256':hashlib.sha256(b'good').hexdigest()}]}))
    assert model_status(verify_hashes=True)['state'] == 'READY'
    (tmp_path / 'graph').write_bytes(b'evil')
    assert model_status(verify_hashes=True)['state'] == 'NOT_READY'


def test_tts_resume_reuses_completed_shot(monkeypatch, tmp_path):
    import numpy as np
    from types import SimpleNamespace
    from src.models.entities import ContentVideoRun
    from src.modules.tao_video_noi_dung import runner
    from src.modules.tao_video_noi_dung.tts_provider import TTSProviderError
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    calls = []
    def synth(config, text, reference):
        calls.append(text)
        if len(calls) == 2:
            raise TTSProviderError('TTS_INFERENCE_TIMEOUT')
        return np.ones(800, dtype=np.float32) * .1, 8000
    monkeypatch.setattr(runner, 'MEDIA_ROOT_DIR', tmp_path)
    monkeypatch.setattr(runner.tts_provider_manager, 'synthesize', synth)
    with Session(engine) as db:
        run = ContentVideoRun(id='run', workspace_id='ws', project_id='proj', plan_id='plan',
            plan_revision=1, storyboard_sha256='a'*64, style_snapshot_sha256='b'*64,
            approval_sha256='c'*64, idempotency_key='tts-resume', created_by='owner',
            steps_json=json.dumps([{'shot_id':'one'},{'shot_id':'two'}]))
        db.add(run)
        db.commit()
        shots = [SimpleNamespace(shot_id='one', narration='Một'), SimpleNamespace(shot_id='two', narration='Hai')]
        with pytest.raises(TTSProviderError):
            runner._prepare_run_tts(db, run, shots, {'provider':'VIE_NEU_V3_TURBO'}, 'token')
        samples, rate = runner._prepare_run_tts(db, run, shots, {'provider':'VIE_NEU_V3_TURBO'}, 'new-token')
        assert calls == ['Một', 'Hai', 'Hai']
        assert rate == 8000
        assert len(samples) == 1600
        assert all(step['tts_audio']['duration_ms'] == 100 for step in json.loads(run.steps_json))
        checkpoints = [step['tts_audio']['storage_key'] for step in json.loads(run.steps_json)]
        assert checkpoints[0].endswith('_token.npz')
        assert checkpoints[1].endswith('_new-toke.npz')


def test_tts_captions_use_measured_shot_audio():
    from types import SimpleNamespace
    from src.modules.tao_video_noi_dung.runner import _tts_captions
    shots = [SimpleNamespace(narration='Một', duration_seconds=10), SimpleNamespace(narration='Hai', duration_seconds=10)]
    cues = _tts_captions(shots, durations_ms=[2200, 4400])
    assert cues[1].start_ms == 2200
    assert cues[1].duration_ms == 4400


def test_pre_submission_quota_pauses_without_marking_submission_uncertain():
    from types import SimpleNamespace
    from src.modules.tao_video_noi_dung.runner import _mark_flow_setup_blocked
    run = SimpleNamespace(status='RUNNING')
    steps = [{'shot_id':'one', 'state':'SUBMITTING'}]
    assert _mark_flow_setup_blocked(run, steps, RuntimeError('FLOW_QUOTA_LIMITED'))
    assert run.status == 'BLOCKED_FLOW_QUOTA'
    assert run.error_code == 'FLOW_QUOTA_LIMITED'
    assert steps[0]['state'] == 'READY'


def test_worker_health_requires_fresh_heartbeat(monkeypatch, tmp_path):
    import time
    from src.runtime_status import write_worker_heartbeat, worker_status
    path = tmp_path / 'worker.json'
    monkeypatch.setenv('WORKER_HEARTBEAT_PATH', str(path))
    assert worker_status()['state'] == 'NOT_READY'
    write_worker_heartbeat()
    assert worker_status()['state'] == 'READY'
    path.write_text(json.dumps({'updated_at': time.time() - 60}))
    assert worker_status()['state'] == 'NOT_READY'


@pytest.mark.parametrize("flag", ["DEV_AUTH_BYPASS", "ALLOW_LOCAL_TEST_SYNTH"])
def test_production_rejects_dev_or_fake_flags(monkeypatch, flag):
    from src.runtime_status import validate_production_runtime
    monkeypatch.setenv('APP_ENV','production')
    monkeypatch.setenv('TESTING','0')
    monkeypatch.setenv('DEV_AUTH_BYPASS','0')
    monkeypatch.setenv(flag,'1')
    with pytest.raises(RuntimeError, match=f'PRODUCTION_UNSAFE_FLAG:{flag}'):
        validate_production_runtime()


def test_ffmpeg_uses_two_threads_for_filter_and_output(monkeypatch):
    import subprocess
    from src.media_process import run_media_command
    commands = []
    monkeypatch.setattr(subprocess, 'run', lambda command, **kwargs: commands.append(command))
    run_media_command(['/usr/bin/ffmpeg', '-i', 'input.mp4', '-c:v', 'libx264', 'output.mp4'])
    command = commands[0]
    assert command[command.index('-filter_threads') + 1] == '2'
    assert command[command.index('-filter_complex_threads') + 1] == '2'
    assert command[-3:] == ['-threads', '2', 'output.mp4']


def test_ffmpeg_bounds_decoder_threads_before_each_input(monkeypatch):
    import subprocess
    from src.media_process import run_media_command
    commands = []
    monkeypatch.setattr(subprocess, 'run', lambda command, **kwargs: commands.append(command))
    run_media_command(['/usr/bin/ffmpeg', '-i', 'video.mp4', '-i', 'overlay.mov', '-filter_complex', 'x', 'output.mp4'])
    command = commands[0]
    input_positions = [index for index, value in enumerate(command) if value == '-i']
    assert [command[index - 2:index] for index in input_positions] == [['-threads:v', '2'], ['-threads:v', '2']]
