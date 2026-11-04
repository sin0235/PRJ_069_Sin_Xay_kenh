"""API worker: mọi đầu vào/tệp đều bị giới hạn vào tác vụ đã được BE tạo."""
import time
import uuid
from fastapi import APIRouter, Request, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from .identity import verify_oidc
from .service import get_store, RemoteTaskError, MAX_CHUNK

router = APIRouter(prefix='/v1/remote-tasks', tags=['Kiểm thử từ xa'])


def bearer(request):
    value = request.headers.get('authorization', '')
    if not value.startswith('Bearer ') or len(value) > 22000:
        raise HTTPException(401, 'REMOTE_AUTH_REQUIRED')
    return value[7:]


@router.post('/claim')
async def claim(request: Request, session_id: str):
    import os
    if os.getenv('REMOTE_COMPUTE_MODE') != 'github':
        raise HTTPException(404, 'REMOTE_DISABLED')
    try:
        uuid.UUID(session_id)
        claims = verify_oidc(bearer(request))
        store = get_store()
        with store.connect() as db:
            session = db.execute('SELECT * FROM runner_session WHERE id=1').fetchone()
            pooled = db.execute('SELECT * FROM runner_pools WHERE session_id=?', (session_id,)).fetchone()
            if pooled:
                session, pipeline = pooled, pooled['pipeline']
                if pipeline != 'AUTO_EDIT':
                    raise RemoteTaskError('REMOTE_SESSION_REJECTED')
            else:
                pipeline = 'AI_VIDEO'
            if not session or session['session_id'] != session_id or (session['run_id'] and session['run_id'] != str(claims['run_id'])):
                raise RemoteTaskError('REMOTE_SESSION_REJECTED')
            if pooled:
                db.execute('UPDATE runner_pools SET updated=?,run_id=?,ready=1 WHERE session_id=?', (time.time(), str(claims['run_id']), session_id))
            else:
                db.execute('UPDATE runner_session SET updated=?,run_id=?,ready=1 WHERE id=1', (time.time(), str(claims['run_id'])))
        claimed = store.claim(str(claims['run_id']), pipeline=pipeline)
        if claimed is None:
            return JSONResponse({'task': None})
        spec, token = claimed
        return {'task': spec, 'token': token}
    except (ValueError, RemoteTaskError):
        raise HTTPException(403, 'REMOTE_CLAIM_REJECTED')


@router.post('/{task}/heartbeat')
def heartbeat(task: uuid.UUID, request: Request):
    get_store().heartbeat(str(task), bearer(request))
    return {'state': 'RUNNING'}


@router.get('/{task}/inputs/{index}')
def download(task: uuid.UUID, index: int, request: Request):
    path = get_store().input_path(str(task), bearer(request), index)
    return FileResponse(path, headers={'Cache-Control': 'no-store', 'Accept-Ranges': 'bytes'})


@router.put('/{task}/output')
async def upload(task: uuid.UUID, request: Request, offset: int = 0):
    store, token = get_store(), bearer(request)
    store.validate_access(str(task), token)
    try:
        length = int(request.headers.get('content-length', '0'))
    except ValueError:
        raise HTTPException(400, 'REMOTE_CHUNK_INVALID')
    if not 0 < length <= MAX_CHUNK:
        raise HTTPException(413, 'REMOTE_CHUNK_TOO_LARGE')
    received, next_offset = 0, offset
    async for block in request.stream():
        if received + len(block) > length:
            raise HTTPException(413, 'REMOTE_CHUNK_TOO_LARGE')
        for start in range(0, len(block), 1024 * 1024):
            piece = block[start:start + 1024 * 1024]
            next_offset = store.append(str(task), token, offset + received, piece)
            received += len(piece)
    if received != length:
        raise HTTPException(400, 'REMOTE_CHUNK_INCOMPLETE')
    return {'next_offset': next_offset}


async def bounded_json(request):
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > 2_000_000:
            raise HTTPException(413, 'REMOTE_RESULT_TOO_LARGE')
    import json
    try:
        value = json.loads(data)
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, TypeError):
        raise HTTPException(400, 'REMOTE_RESULT_INVALID')


@router.post('/{task}/complete')
async def complete(task: uuid.UUID, request: Request):
    get_store().validate_access(str(task), bearer(request), finished=True)
    payload = await bounded_json(request)
    get_store().complete(str(task), bearer(request), payload.get('result', {}), payload.get('output'))
    return {'state': 'SUCCEEDED'}


@router.post('/{task}/fail')
async def fail(task: uuid.UUID, request: Request):
    get_store().validate_access(str(task), bearer(request))
    payload = await bounded_json(request)
    get_store().fail(str(task), bearer(request), str(payload.get('error', 'REMOTE_ENGINE_FAILED')))
    return {'state': 'FAILED'}
