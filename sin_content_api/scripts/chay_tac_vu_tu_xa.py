"""Worker kiểm thử GitHub: OIDC, stream tệp, heartbeat, chạy stage và trả kết quả theo khối."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['REMOTE_ENGINE_CHILD'] = '1'
os.environ['CONTENT_VIDEO_WORKER_ENABLED'] = '0'
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['OPENBLAS_NUM_THREADS'] = '2'
os.environ['MKL_NUM_THREADS'] = '2'

from src.modules.tac_vu_tu_xa.service import file_hash


def oidc(origin):
    endpoint = os.environ['ACTIONS_ID_TOKEN_REQUEST_URL']
    headers = {'Authorization': 'Bearer ' + os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']}
    response = httpx.get(endpoint, params={'audience': origin}, headers=headers, timeout=20)
    response.raise_for_status()
    return response.json()['value']


def request(client, method, url, **kwargs):
    for attempt in range(4):
        try:
            response = client.request(method, url, **kwargs)
            if response.status_code not in {429, 502, 503, 504}:
                response.raise_for_status()
                return response
        except httpx.TransportError:
            if attempt == 3:
                raise
        time.sleep(2 ** attempt)
    raise RuntimeError('REMOTE_NETWORK_UNAVAILABLE')


def process(client, base, spec, token):
    task_url = base + '/' + spec['id']
    headers = {'Authorization': 'Bearer ' + token}
    stopped = threading.Event()
    errors = []
    def heartbeat():
        while not stopped.wait(30):
            try:
                request(client, 'POST', task_url + '/heartbeat', headers=headers)
            except Exception:
                errors.append('REMOTE_HEARTBEAT_FAILED')
                return
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix='prj069_remote_') as temporary:
            root = Path(temporary)
            total = sum(item['size'] for item in spec['inputs'])
            if shutil.disk_usage(root).free < total + 3 * 1024 ** 3:
                raise RuntimeError('REMOTE_DISK_BUDGET_EXCEEDED')
            inputs = []
            for index, item in enumerate(spec['inputs']):
                path = root / f'input_{index}{Path(item["name"]).suffix}'
                digest = hashlib.sha256()
                with client.stream('GET', task_url + f'/inputs/{index}', headers=headers) as response:
                    response.raise_for_status()
                    with path.open('wb') as output:
                        for chunk in response.iter_bytes(1024 * 1024):
                            if output.tell() + len(chunk) > item['size']:
                                raise RuntimeError('REMOTE_INPUT_TOO_LARGE')
                            output.write(chunk)
                            digest.update(chunk)
                if path.stat().st_size != item['size'] or digest.hexdigest() != item['sha256']:
                    raise RuntimeError('REMOTE_INPUT_HASH_MISMATCH')
                inputs.append(path)
            from src.modules.tac_vu_tu_xa.stages import execute_stage
            suffix = spec['parameters'].get('output_suffix') or '.mp4'
            if suffix not in {'.wav', '.m4a', '.mp3', '.mp4', '.mov', '.png', '.jpg', '.webm'}:
                raise RuntimeError('REMOTE_OUTPUT_SUFFIX_INVALID')
            if spec['parameters']['operation'] == 'render_scene' and spec['parameters']['arguments'].get('transparent_background'):
                suffix = '.mov'
            output = root / ('output' + suffix)
            result = execute_stage(spec, inputs, output)
            if errors:
                raise RuntimeError(errors[0])
            manifest = None
            if output.is_file():
                manifest = {'size': output.stat().st_size, 'sha256': file_hash(output)}
                offset = 0
                with output.open('rb') as source:
                    while chunk := source.read(16 * 1024 * 1024):
                        response = request(client, 'PUT', task_url + '/output', params={'offset': offset}, headers=headers, content=chunk)
                        offset = response.json()['next_offset']
                        source.seek(offset)
            request(client, 'POST', task_url + '/complete', headers=headers, json={'result': result, 'output': manifest})
            print(json.dumps({'task': spec['id'], 'stage': spec['stage'], 'state': 'SUCCEEDED',
                              'output_bytes': manifest['size'] if manifest else 0}), flush=True)
    except Exception as exc:
        # Nhật ký chỉ chứa mã/lớp lỗi; thông báo thư viện có thể chứa header hoặc đường dẫn riêng.
        code = str(exc) if str(exc).startswith(('REMOTE_', 'VIDEO_', 'FLOW_')) and len(str(exc)) < 150 else type(exc).__name__
        try:
            request(client, 'POST', task_url + '/fail', headers=headers, json={'error': code})
        finally:
            print(json.dumps({'task': spec['id'], 'state': 'FAILED', 'error': code}), flush=True)
    finally:
        stopped.set()
        thread.join(timeout=25)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--origin', required=True)
    parser.add_argument('--session-id', required=True)
    args = parser.parse_args()
    origin = args.origin.rstrip('/')
    if origin != os.environ['REMOTE_EXPECTED_ORIGIN'].rstrip('/') or urlsplit(origin).scheme != 'https':
        raise SystemExit('REMOTE_ORIGIN_REJECTED')
    base = origin + '/v1/remote-tasks'
    deadline = time.monotonic() + 5 * 3600
    last_task = time.monotonic()
    with httpx.Client(timeout=httpx.Timeout(180, connect=20), follow_redirects=False) as client:
        while time.monotonic() < deadline and time.monotonic() - last_task < 300:
            response = request(client, 'POST', base + '/claim', params={'session_id': args.session_id},
                               headers={'Authorization': 'Bearer ' + oidc(origin)})
            data = response.json()
            if data.get('task'):
                last_task = time.monotonic()
                process(client, base, data['task'], data['token'])
                last_task = time.monotonic()
            else:
                time.sleep(5)


if __name__ == '__main__':
    main()
