"""Điều phối stage đồng bộ trong worker local; HTTP của người dùng vẫn trả job ID ngay."""
from contextvars import ContextVar
from functools import wraps
import inspect
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
from .service import get_store, RemoteTaskError

scope = ContextVar('remote_scope', default=None)


def enabled():
    return os.getenv('REMOTE_COMPUTE_MODE') == 'github' and os.getenv('REMOTE_ENGINE_CHILD') != '1'


def ensure_runner(store):
    now = time.time()
    with store.connect() as db:
        row = db.execute('SELECT * FROM runner_session WHERE id=1').fetchone()
        if row and row['updated'] > now - 240:
            return
        session_id = str(uuid.uuid4())
        db.execute('INSERT OR REPLACE INTO runner_session(id,updated,session_id) VALUES(1,?,?)', (now, session_id))
    repo = os.environ['REMOTE_GITHUB_REPOSITORY']
    ref = os.environ['REMOTE_GITHUB_REF']
    origin = os.environ['REMOTE_PUBLIC_ORIGIN'].rstrip('/')
    if not origin.startswith('https://'):
        raise RemoteTaskError('REMOTE_HTTPS_REQUIRED')
    # Chế độ dev chỉ bật tường minh; gh giữ phiên đăng nhập, BE không đọc hay lưu token của CLI.
    if os.getenv('REMOTE_GITHUB_DISPATCH') != 'gh':
        raise RemoteTaskError('REMOTE_DISPATCH_NOT_CONFIGURED')
    result = subprocess.run(['gh', 'workflow', 'run', 'kiem_thu_video_tu_xa.yaml', '--repo', repo, '--ref', ref,
                             '-f', f'origin={origin}', '-f', f'session_id={session_id}'],
                            capture_output=True, text=True, timeout=30)
    if result.returncode:
        with store.connect() as db:
            db.execute('DELETE FROM runner_session WHERE session_id=?', (session_id,))
        raise RemoteTaskError('REMOTE_DISPATCH_FAILED')


def execute(stage, operation, arguments, inputs, output=None):
    context = scope.get()
    if context is None:
        raise RemoteTaskError('REMOTE_WORKSPACE_CONTEXT_REQUIRED')
    store = get_store()
    suffix = Path(output).suffix.lower() if output is not None else None
    task = store.create(stage, {'operation': operation, 'arguments': arguments, 'output_suffix': suffix}, inputs, context['workspace'], context['pipeline'])
    deadline = time.monotonic() + 5 * 3600
    try:
        ensure_runner(store)
        while time.monotonic() < deadline:
            row = store.get(task)
            if row['state'] == 'SUCCEEDED':
                if output is not None:
                    source = store.output_path(task)
                    if not source.is_file():
                        raise RemoteTaskError('REMOTE_OUTPUT_MISSING')
                    output = Path(output)
                    output.parent.mkdir(parents=True, exist_ok=True)
                    import shutil
                    staging = output.with_name(output.name + '.remote-part')
                    shutil.copyfile(source, staging)
                    staging.replace(output)
                    source.unlink()
                return json.loads(row['result'])
            if row['state'] in {'FAILED', 'LOST', 'CANCELLED'}:
                raise RemoteTaskError(row['error'] or 'REMOTE_TASK_STOPPED')
            if row['state'] in {'RUNNING', 'UPLOADING'} and row['lease_until'] < time.time():
                raise RemoteTaskError('REMOTE_LEASE_LOST')
            if row['state'] == 'QUEUED':
                ensure_runner(store)
            if context.get('parent_id'):
                from src.database import SessionLocal
                from src.models.entities import AIGenerationJob, ContentVideoRun
                with SessionLocal() as db:
                    parent = db.get(AIGenerationJob if context.get('parent_type') == 'MEDIA_JOB' else ContentVideoRun, context['parent_id'])
                    state = (getattr(parent, 'state', None) or getattr(parent, 'status', None)) if parent else 'CANCELLED'
                    if state in {'CANCELLED', 'FAILED', 'DELETED'}:
                        raise RemoteTaskError('REMOTE_PARENT_STOPPED')
            time.sleep(2)
        raise RemoteTaskError('REMOTE_STAGE_TIMEOUT')
    except BaseException:
        store.cancel(task)
        raise


def pipeline(kind):
    """Giữ scope theo thread điều phối, không suy ra quyền từ tên file do runner gửi."""
    def decorate(function):
        signature = inspect.signature(function)
        @wraps(function)
        def call(*args, **kwargs):
            if not enabled():
                return function(*args, **kwargs)
            bound = signature.bind(*args, **kwargs).arguments
            if kind == 'AUTO_EDIT':
                context = {'workspace': bound['workspace_id'], 'pipeline': kind, 'parent_id': bound.get('job_id'), 'parent_type': 'MEDIA_JOB'}
            elif kind == 'MEDIA_JOB':
                from src.models.entities import ProductionProject
                job = bound['job']
                project = bound['db'].get(ProductionProject, job.project_id) if job.project_id else None
                context = {'workspace': job.workspace_id, 'pipeline': project.workflow_type if project else 'AI_VIDEO',
                           'parent_id': job.id, 'parent_type': 'MEDIA_JOB'}
            else:
                from src.database import SessionLocal
                from src.models.entities import ContentVideoRun
                with SessionLocal() as db:
                    run = db.get(ContentVideoRun, bound['run_id'])
                    if run is None:
                        return function(*args, **kwargs)
                    context = {'workspace': run.workspace_id, 'pipeline': kind, 'parent_id': run.id}
            token = scope.set(context)
            try:
                return function(*args, **kwargs)
            finally:
                scope.reset(token)
        return call
    return decorate


def offload(operation, stage, output=None):
    """Chỉ các hàm engine khai báo tường minh mới được thực thi từ xa."""
    def decorate(function):
        signature = inspect.signature(function)
        @wraps(function)
        def call(*args, **kwargs):
            if not enabled():
                return function(*args, **kwargs)
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            values = dict(bound.arguments)
            values.pop('self', None)
            values.pop('temp_dir', None)
            output_path = Path(values.pop(output)) if output else None
            inputs = []
            def encode(value):
                if isinstance(value, Path):
                    path = value.resolve(strict=True)
                    if path not in inputs:
                        inputs.append(path)
                    return {'remote_input': inputs.index(path)}
                if hasattr(value, 'model_dump'):
                    return {'remote_model': type(value).__name__, 'value': value.model_dump(mode='json')}
                if isinstance(value, dict):
                    return {key: encode(item) for key, item in value.items()}
                if isinstance(value, (tuple, list)):
                    return [encode(item) for item in value]
                return value
            if operation == 'render_timeline':
                resolver = values.pop('asset_path_resolver')
                timeline = values['timeline']
                document = timeline.model_dump(mode='json') if hasattr(timeline, 'model_dump') else timeline
                ids = set()
                def collect(value):
                    if isinstance(value, dict):
                        for key, item in value.items():
                            if key.endswith('asset_id') and isinstance(item, str) and item:
                                ids.add(item)
                            else:
                                collect(item)
                    elif isinstance(value, list):
                        for item in value:
                            collect(item)
                collect(document)
                values['asset_paths'] = {asset: resolver(asset) for asset in sorted(ids)}
            if operation == 'tts' and values.get('reference_path'):
                values['reference_path'] = Path(values['reference_path'])
            if operation == 'brand_end':
                values['video_path'] = Path(output_path)
            if operation == 'tts':
                import tempfile
                with tempfile.TemporaryDirectory(prefix='remote_tts_') as temporary:
                    wav = Path(temporary) / 'voice.wav'
                    execute(stage, operation, encode(values), inputs, wav)
                    import soundfile as sf
                    audio, rate = sf.read(wav, dtype='float32')
                    return audio, rate
            return execute(stage, operation, encode(values), inputs, output_path)
        return call
    return decorate
