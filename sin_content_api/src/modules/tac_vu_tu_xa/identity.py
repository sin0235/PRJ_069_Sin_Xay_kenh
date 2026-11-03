"""Xác minh OIDC GitHub bằng khóa công khai cố định nguồn, không tin khóa trong JWT."""
import base64
import json
import os
import time
import threading
import httpx
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes
from .service import RemoteTaskError

ISSUER = 'https://token.actions.githubusercontent.com'
_cache = (0, {})
_lock = threading.Lock()


def decode(value):
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


def public_keys():
    global _cache
    with _lock:
        if _cache[0] > time.time():
            return _cache[1]
        response = httpx.get(ISSUER + '/.well-known/jwks', timeout=10, follow_redirects=False)
        response.raise_for_status()
        keys = {}
        for key in response.json()['keys']:
            if key.get('kty') == 'RSA' and key.get('alg') == 'RS256':
                numbers = rsa.RSAPublicNumbers(int.from_bytes(decode(key['e']), 'big'), int.from_bytes(decode(key['n']), 'big'))
                if numbers.n.bit_length() >= 2048:
                    keys[key['kid']] = numbers.public_key()
        _cache = (time.time() + 300, keys)
        return keys


def verify_oidc(token: str) -> dict:
    try:
        if len(token) > 20000:
            raise ValueError()
        head, body, signature = token.split('.')
        header, claims = json.loads(decode(head)), json.loads(decode(body))
        if header.get('alg') != 'RS256':
            raise ValueError()
        key = public_keys()[header['kid']]
        key.verify(decode(signature), f'{head}.{body}'.encode('ascii'), padding.PKCS1v15(), hashes.SHA256())
        repo, repo_id, ref, origin = (os.environ[name] for name in (
            'REMOTE_GITHUB_REPOSITORY', 'REMOTE_GITHUB_REPOSITORY_ID', 'REMOTE_GITHUB_REF', 'REMOTE_PUBLIC_ORIGIN'))
        expected = {'iss': ISSUER, 'aud': origin.rstrip('/'), 'repository': repo, 'repository_id': repo_id,
                    'ref': f'refs/heads/{ref}', 'event_name': 'workflow_dispatch',
                    'workflow_ref': f'{repo}/.github/workflows/kiem_thu_video_tu_xa.yaml@refs/heads/{ref}'}
        if any(claims.get(name) != value for name, value in expected.items()):
            raise ValueError()
        now = time.time()
        if not now < float(claims['exp']) <= now + 1200 or float(claims['nbf']) > now + 30 or float(claims['iat']) > now + 30:
            raise ValueError()
        if not str(claims['run_id']).isdigit() or not str(claims['sub']):
            raise ValueError()
        return claims
    except Exception as exc:
        raise RemoteTaskError('REMOTE_OIDC_REJECTED') from exc
