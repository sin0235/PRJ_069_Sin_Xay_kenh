"""Tải đầu vào theo luồng và tiếp tục bằng Range khi mất kết nối."""
import time
import httpx
from .service import file_hash


def download_input(client, url, headers, path, size, sha256):
    for attempt in range(4):
        offset = path.stat().st_size if path.exists() else 0
        if offset == size:
            break
        request_headers = {**headers, 'Range': f'bytes={offset}-'} if offset else headers
        try:
            with client.stream('GET', url, headers=request_headers) as response:
                response.raise_for_status()
                if offset and response.status_code == 206:
                    expected = f'bytes {offset}-{size - 1}/{size}'
                    if response.headers.get('content-range') != expected:
                        raise RuntimeError('REMOTE_INPUT_RANGE_INVALID')
                elif response.status_code == 200:
                    offset = 0
                else:
                    raise RuntimeError('REMOTE_INPUT_RANGE_INVALID')
                with path.open('ab' if offset else 'wb') as output:
                    for chunk in response.iter_bytes(1024 * 1024):
                        if output.tell() + len(chunk) > size:
                            raise RuntimeError('REMOTE_INPUT_TOO_LARGE')
                        output.write(chunk)
            if path.stat().st_size == size:
                break
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            if (attempt == 3 or isinstance(exc, httpx.HTTPStatusError)
                    and exc.response.status_code not in {408, 429, 500, 502, 503, 504}):
                raise
        time.sleep(2 ** attempt)
    if not path.is_file() or path.stat().st_size != size or file_hash(path) != sha256:
        raise RuntimeError('REMOTE_INPUT_HASH_MISMATCH')
