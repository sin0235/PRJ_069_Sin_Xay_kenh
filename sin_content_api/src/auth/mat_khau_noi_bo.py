"""Băm mật khẩu cục bộ và ký phiên ngắn hạn bằng cấu hình Baha Auth."""

import base64
import binascii
import hashlib
import hmac
import json
import os
import time

from baha_auth.src.xac_minh_danh_tinh import InvalidBearerToken, VerifiedIdentity, verify_bearer_token


PASSWORD_ITERATIONS = 600_000
SESSION_SECONDS = 8 * 60 * 60
SESSION_COOKIE = "baha_auth_token"


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.b64decode(padded.encode("ascii"), altchars=b"-_", validate=True)


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    if not isinstance(password, str) or not 12 <= len(password) <= 1024:
        raise ValueError("Mật khẩu phải dài từ 12 đến 1024 ký tự.")
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${_encode(salt)}${_encode(digest)}"


def verify_password(password: str, encoded: str | None) -> bool:
    try:
        if not isinstance(password, str):
            return False
        if encoded is None:
            hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), b"\0" * 16, PASSWORD_ITERATIONS)
            return False
        if not isinstance(encoded, str):
            return False
        algorithm, iteration_text, salt_text, digest_text = encoded.split("$", 3)
        iterations = int(iteration_text)
        if algorithm != "pbkdf2_sha256" or not 100_000 <= iterations <= 1_000_000:
            return False
        expected = _decode(digest_text)
        if not expected or len(expected) != hashlib.sha256().digest_size:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), _decode(salt_text), iterations)
        return hmac.compare_digest(actual, expected)
    except (AttributeError, TypeError, ValueError, UnicodeEncodeError, binascii.Error):
        return False


def create_session_token(
    user_id: str,
    workspace_id: str,
    *,
    secret: str,
    issuer: str,
    audience: str,
    now: int | None = None,
    lifetime_seconds: int = SESSION_SECONDS,
) -> str:
    if not all(isinstance(value, str) and value.strip() for value in (user_id, workspace_id, secret, issuer, audience)):
        raise ValueError("Thiếu cấu hình hoặc danh tính phiên.")
    if len(workspace_id) > 36 or not 1 <= lifetime_seconds <= SESSION_SECONDS:
        raise ValueError("Thời hạn hoặc workspace phiên không hợp lệ.")

    issued_at = int(time.time()) if now is None else int(now)
    header = _encode(b'{"alg":"HS256","typ":"JWT"}')
    claims = _encode(json.dumps({
        "sub": user_id,
        "iss": issuer,
        "aud": audience,
        "iat": issued_at,
        "exp": issued_at + lifetime_seconds,
        "workspace_id": workspace_id,
    }, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header}.{claims}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header}.{claims}.{_encode(signature)}"


def verify_session_token(
    token: str,
    *,
    secret: str,
    issuer: str,
    audience: str,
    expected_workspace_id: str | None = None,
) -> VerifiedIdentity:
    identity = verify_bearer_token(token, secret=secret, issuer=issuer, audience=audience)
    if expected_workspace_id and identity.workspace_id != expected_workspace_id:
        raise InvalidBearerToken("INVALID_WORKSPACE_ID")
    return identity
