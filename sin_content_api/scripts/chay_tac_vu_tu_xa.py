"""Worker kiểm thử GitHub: OIDC, stream tệp, heartbeat, chạy stage và trả kết quả theo khối."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import subprocess
import signal
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
from src.modules.tac_vu_tu_xa.transfer import download_input


def stage_child(payload_path):
    from src.modules.tac_vu_tu_xa.stages import execute_stage
    payload = json.loads(Path(payload_path).read_text(encoding='utf-8'))
    try:
        result = execute_stage(payload['spec'], [Path(item) for item in payload['inputs']], Path(payload['output']))
        receipt = {'result': result}
    except Exception as exc:
        import re
        code = str(exc).split(':', 1)[0]
        receipt = {'error': code if re.fullmatch('[A-Z0-9_]{1,150}', code) else type(exc).__name__}
    Path(payload['receipt']).write_text(json.dumps(receipt, ensure_ascii=False), encoding='utf-8')
    return 1 if 'error' in receipt else 0


def execute_isolated(spec, inputs, output, root, heartbeat_errors):
    payload_path, receipt = root / 'stage.json', root / 'receipt.json'
    payload_path.write_text(json.dumps({'spec': spec, 'inputs': [str(path) for path in inputs],
                                      'output': str(output), 'receipt': str(receipt)}), encoding='utf-8')
    started = time.monotonic()
    peak_rss, peak_scratch = 0, 0
    with (root / 'engine.log').open('wb') as log:
        process = subprocess.Popen([sys.executable, __file__, '--execute-stage', str(payload_path)],
                                   stdout=log, stderr=log, start_new_session=True)
        try:
            while process.poll() is None:
                # Đo cả cây Chromium/FFmpeg, không chỉ RSS của Python cha.
                rows = subprocess.check_output(['ps', '-eo', 'pid=,ppid=,rss='], text=True)
                entries = [tuple(map(int, row.split())) for row in rows.splitlines() if row.strip()]
                owned = {process.pid}
                while True:
                    descendants = {pid for pid, parent, _ in entries if parent in owned}
                    if descendants <= owned:
                        break
                    owned |= descendants
                rss = sum(size * 1024 for pid, _, size in entries if pid in owned)
                peak_rss = max(peak_rss, rss)
                scratch_size = 0
                for path in root.rglob('*'):
                    try:
                        if path.is_file():
                            scratch_size += path.stat().st_size
                    except FileNotFoundError:
                        pass
                peak_scratch = max(peak_scratch, scratch_size)
                if heartbeat_errors:
                    raise RuntimeError(heartbeat_errors[0])
                if rss > 6 * 1024 ** 3:
                    raise RuntimeError('REMOTE_MEMORY_BUDGET_EXCEEDED')
                if shutil.disk_usage(root).free < 512 * 1024 ** 2:
                    raise RuntimeError('REMOTE_DISK_BUDGET_EXCEEDED')
                if time.monotonic() - started > 7200:
                    raise RuntimeError('REMOTE_STAGE_TIMEOUT')
                time.sleep(2)
        finally:
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=20)
    if not receipt.is_file():
        raise RuntimeError('REMOTE_ENGINE_PROCESS_FAILED')
    result = json.loads(receipt.read_text(encoding='utf-8'))
    if 'error' in result:
        raise RuntimeError(result['error'])
    return result['result'], {'peak_rss_bytes': peak_rss, 'peak_scratch_bytes': peak_scratch,
                              'elapsed_seconds': round(time.monotonic() - started, 2)}


def oidc(origin):
    endpoint = os.environ['ACTIONS_ID_TOKEN_REQUEST_URL']
    headers = {'Authorization': 'Bearer ' + os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']}
    for attempt in range(4):
        try:
            response = httpx.get(endpoint, params={'audience': origin}, headers=headers, timeout=20)
            if response.status_code in {429, 502, 503, 504}:
                raise httpx.ReadTimeout('OIDC temporarily unavailable')
            response.raise_for_status()
            return response.json()['value']
        except httpx.TransportError:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


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
                download_input(client, task_url + f'/inputs/{index}', headers, path, item['size'], item['sha256'])
                inputs.append(path)
            suffix = spec['parameters'].get('output_suffix') or '.mp4'
            if suffix not in {'.wav', '.m4a', '.mp3', '.mp4', '.mov', '.png', '.jpg', '.webm'}:
                raise RuntimeError('REMOTE_OUTPUT_SUFFIX_INVALID')
            if spec['parameters']['operation'] == 'render_scene' and spec['parameters']['arguments'].get('transparent_background'):
                suffix = '.mov'
            output = root / ('output' + suffix)
            result, metrics = execute_isolated(spec, inputs, output, root, errors)
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
                              'output_bytes': manifest['size'] if manifest else 0, **metrics}), flush=True)
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
            try:
                response = request(client, 'POST', base + '/claim', params={'session_id': args.session_id},
                                   headers={'Authorization': 'Bearer ' + oidc(origin)})
            except httpx.TransportError:
                print(json.dumps({'state': 'RECONNECTING', 'error': 'REMOTE_CONTROL_TIMEOUT'}), flush=True)
                time.sleep(10)
                continue
            data = response.json()
            if data.get('task'):
                last_task = time.monotonic()
                process(client, base, data['task'], data['token'])
                last_task = time.monotonic()
            else:
                time.sleep(5)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--execute-stage':
        raise SystemExit(stage_child(sys.argv[2]))
    main()
