"""Băm mật khẩu Founder và ký phiên cục bộ của một workspace."""

import base64
import hashlib
import hmac
import json
import os
import time

from baha_auth.src.xac_minh_danh_tinh import InvalidBearerToken, VerifiedIdentity, verify_bearer_token


PASSWORD_ITERATIONS = 600_000
SESSION_SECONDS = 8 * 60 * 60
SESSION_COOKIE = "sin_local_session"


def local_password_mode(app_env: str) -> bool:
    # Cho phép đăng nhập mật khẩu Founder thật trên cả local và production
    return (
        os.getenv("AUTH_MODE", "").strip().casefold() == "local_password"
        or bool(os.getenv("FOUNDER_EMAIL") and os.getenv("FOUNDER_PASSWORD_HASH"))
    )


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    if not isinstance(password, str) or len(password) < 12:
        raise ValueError("Mật khẩu phải có ít nhất 12 ký tự.")
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    encode = lambda value: base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${encode(salt)}${encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iteration_text, salt_text, digest_text = encoded.split("$", 3)
        iterations = int(iteration_text)
        if algorithm != "pbkdf2_sha256" or not 100_000 <= iterations <= 1_000_000:
            return False
        decode = lambda value: base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        expected = decode(digest_text)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), decode(salt_text), iterations)
        return hmac.compare_digest(actual, expected)
    except (AttributeError, TypeError, ValueError, UnicodeEncodeError):
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
    if len(workspace_id) > 36 or lifetime_seconds < 1 or lifetime_seconds > SESSION_SECONDS:
        raise ValueError("Thời hạn hoặc workspace phiên không hợp lệ.")

    encode = lambda value: base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")
    header = encode(b'{"alg":"HS256","typ":"JWT"}')
    claims = encode(json.dumps({
        "sub": user_id,
        "iss": issuer,
        "aud": audience,
        "iat": int(time.time()) if now is None else int(now),
        "exp": (int(time.time()) if now is None else int(now)) + lifetime_seconds,
        "workspace_id": workspace_id,
    }, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header}.{claims}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header}.{claims}.{encode(signature)}"


def verify_session_token(
    token: str,
    *,
    secret: str,
    issuer: str,
    audience: str,
    expected_workspace_id: str | None = None,
    now: int | None = None,
) -> VerifiedIdentity:
    identity = verify_bearer_token(token, secret=secret, issuer=issuer, audience=audience)
    if expected_workspace_id and identity.workspace_id != expected_workspace_id:
        raise InvalidBearerToken("INVALID_WORKSPACE_ID")
    if now is not None and identity.expires_at <= now:
        raise InvalidBearerToken("TOKEN_EXPIRED")
    return identity
