"""Hàng đợi bền vững chỉ do BE local sở hữu; runner không nhận DB hoặc đường dẫn host."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
import uuid

STAGES = {'EXTRACT_AUDIO', 'TRANSCRIBE', 'TTS', 'PREPARE_FLOW_ASSET', 'RENDER_VISUAL', 'RENDER_FINAL', 'QC'}
ACTIVE = {'RUNNING', 'UPLOADING'}
MAX_CHUNK = 64 * 1024 * 1024


class RemoteTaskError(ValueError):
    pass


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


class TaskStore:
    def __init__(self, database: Path, root: Path):
        self.database, self.root = database, root
        database.parent.mkdir(parents=True, exist_ok=True)
        root.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, stage TEXT NOT NULL, workspace TEXT NOT NULL,
                pipeline TEXT NOT NULL, parameters TEXT NOT NULL, inputs TEXT NOT NULL,
                state TEXT NOT NULL, token_hash TEXT, lease_until REAL, runner TEXT,
                created REAL NOT NULL, result TEXT, output_manifest TEXT, error TEXT)''')
            db.execute('CREATE TABLE IF NOT EXISTS runner_session (id INTEGER PRIMARY KEY CHECK(id=1), updated REAL NOT NULL, session_id TEXT NOT NULL, run_id TEXT)')
            columns = {row['name'] for row in db.execute('PRAGMA table_info(runner_session)')}
            if 'ready' not in columns:
                db.execute('ALTER TABLE runner_session ADD COLUMN ready INTEGER NOT NULL DEFAULT 0')
                db.execute("UPDATE runner_session SET ready=1 WHERE run_id IN (SELECT runner FROM tasks WHERE runner IS NOT NULL)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA busy_timeout=30000')
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def create(self, stage: str, parameters: dict, paths: list[Path], workspace: str, pipeline: str) -> str:
        if stage not in STAGES or pipeline not in {'AUTO_EDIT', 'AI_VIDEO'} or not workspace:
            raise RemoteTaskError('REMOTE_SPEC_INVALID')
        if len(paths) > 100 or len(json.dumps(parameters)) > 2_000_000:
            raise RemoteTaskError('REMOTE_SPEC_TOO_LARGE')
        inputs = []
        for path in paths:
            path = Path(path).resolve(strict=True)
            if not path.is_file():
                raise RemoteTaskError('REMOTE_INPUT_INVALID')
            inputs.append({'path': str(path), 'name': f'i{len(inputs)}{path.suffix.lower()}',
                           'size': path.stat().st_size, 'sha256': file_hash(path)})
        task = str(uuid.uuid4())
        with self.connect() as db:
            db.execute('INSERT INTO tasks(id,stage,workspace,pipeline,parameters,inputs,state,created) VALUES(?,?,?,?,?,?,?,?)',
                       (task, stage, workspace, pipeline, json.dumps(parameters), json.dumps(inputs), 'QUEUED', time.time()))
        return task

    def get(self, task: str) -> dict:
        with self.connect() as db:
            row = db.execute('SELECT * FROM tasks WHERE id=?', (task,)).fetchone()
            if row is None:
                raise RemoteTaskError('REMOTE_TASK_NOT_FOUND')
            return dict(row)

    def claim(self, runner: str):
        token = secrets.token_urlsafe(32)
        now = time.time()
        with self.connect() as db:
            db.execute("UPDATE tasks SET state='LOST',token_hash=NULL,error='REMOTE_LEASE_LOST' WHERE state IN ('RUNNING','UPLOADING') AND lease_until<=?", (now,))
            if db.execute("SELECT 1 FROM tasks WHERE state IN ('RUNNING','UPLOADING')").fetchone():
                return None
            row = db.execute("SELECT * FROM tasks WHERE state='QUEUED' ORDER BY created LIMIT 1").fetchone()
            if row is None:
                return None
            db.execute("UPDATE tasks SET state='RUNNING',token_hash=?,lease_until=?,runner=? WHERE id=? AND state='QUEUED'",
                       (hashlib.sha256(token.encode()).hexdigest(), now + 300, runner, row['id']))
            spec = {key: row[key] for key in ('id', 'stage', 'workspace', 'pipeline')}
            spec.update(version=1, parameters=json.loads(row['parameters']),
                        inputs=[{key: value for key, value in item.items() if key != 'path'} for item in json.loads(row['inputs'])])
            return spec, token

    def _authorize(self, db, task, token, *, finished=False):
        row = db.execute('SELECT * FROM tasks WHERE id=?', (task,)).fetchone()
        if row is None or not row['token_hash'] or not secrets.compare_digest(
            row['token_hash'], hashlib.sha256(token.encode()).hexdigest()
        ) or (row['state'] not in ACTIVE and not (finished and row['state'] == 'SUCCEEDED')):
            raise RemoteTaskError('REMOTE_TOKEN_REJECTED')
        if row['lease_until'] <= time.time():
            raise RemoteTaskError('REMOTE_TOKEN_EXPIRED')
        return row

    def heartbeat(self, task, token):
        with self.connect() as db:
            row = self._authorize(db, task, token)
            db.execute('UPDATE tasks SET lease_until=? WHERE id=?', (time.time() + 300, task))
            db.execute('UPDATE runner_session SET updated=?,ready=1 WHERE run_id=?', (time.time(), row['runner']))

    def validate_access(self, task, token, *, finished=False):
        with self.connect() as db:
            self._authorize(db, task, token, finished=finished)

    def input_path(self, task, token, index):
        with self.connect() as db:
            row = self._authorize(db, task, token)
            inputs = json.loads(row['inputs'])
            if index < 0 or index >= len(inputs):
                raise RemoteTaskError('REMOTE_INPUT_NOT_FOUND')
            item = inputs[index]
            path = Path(item['path'])
            if not path.is_file() or path.stat().st_size != item['size']:
                raise RemoteTaskError('REMOTE_INPUT_CHANGED')
            return path

    def output_path(self, task):
        uuid.UUID(task)
        return self.root / f'{task}.part'

    def append(self, task, token, offset, data):
        if offset < 0 or not 0 < len(data) <= MAX_CHUNK:
            raise RemoteTaskError('REMOTE_CHUNK_INVALID')
        with self.connect() as db:
            self._authorize(db, task, token)
            path = self.output_path(task)
            size = path.stat().st_size if path.exists() else 0
            if offset < size:
                overlap = min(size - offset, len(data))
                with path.open('rb') as source:
                    source.seek(offset)
                    if not secrets.compare_digest(source.read(overlap), data[:overlap]):
                        raise RemoteTaskError('REMOTE_OFFSET_MISMATCH')
                data = data[overlap:]
                offset += overlap
                if not data:
                    return size
            if offset != size or size + len(data) > 12 * 1024 ** 3:
                raise RemoteTaskError('REMOTE_OFFSET_MISMATCH')
            import shutil
            if shutil.disk_usage(self.root).free < len(data) + 512 * 1024 ** 2:
                raise RemoteTaskError('REMOTE_DISK_FULL')
            with path.open('ab') as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            db.execute("UPDATE tasks SET state='UPLOADING',lease_until=? WHERE id=?", (time.time() + 300, task))
            return size + len(data)

    def complete(self, task, token, result, output):
        if len(json.dumps(result)) > 2_000_000:
            raise RemoteTaskError('REMOTE_RESULT_TOO_LARGE')
        with self.connect() as db:
            row = self._authorize(db, task, token, finished=True)
            serialized = json.dumps(result, sort_keys=True)
            manifest = json.dumps(output, sort_keys=True)
            if row['state'] == 'SUCCEEDED':
                if row['result'] != serialized or row['output_manifest'] != manifest:
                    raise RemoteTaskError('REMOTE_RESULT_CONFLICT')
                return
            path = self.output_path(task)
            if output is not None:
                if not isinstance(output, dict) or not path.is_file() or output.get('size') != path.stat().st_size or output.get('sha256') != file_hash(path):
                    raise RemoteTaskError('REMOTE_RESULT_HASH_MISMATCH')
            elif path.exists():
                raise RemoteTaskError('REMOTE_RESULT_MANIFEST_MISSING')
            db.execute("UPDATE tasks SET state='SUCCEEDED',result=?,output_manifest=? WHERE id=?", (serialized, manifest, task))

    def fail(self, task, token, code):
        with self.connect() as db:
            self._authorize(db, task, token)
            db.execute("UPDATE tasks SET state='FAILED',error=?,token_hash=NULL WHERE id=?", (code[:200], task))

    def cancel(self, task):
        with self.connect() as db:
            db.execute("UPDATE tasks SET state='CANCELLED',token_hash=NULL WHERE id=? AND state NOT IN ('SUCCEEDED','FAILED')", (task,))


def get_store():
    from src.modules.media_studio.security import MEDIA_ROOT_DIR
    root = MEDIA_ROOT_DIR / '.remote'
    return TaskStore(root / 'tasks.sqlite3', root / 'outputs')
