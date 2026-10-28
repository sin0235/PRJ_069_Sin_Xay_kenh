"""Xác minh bearer token do nhà cung cấp bên ngoài phát hành; không tạo token."""

import base64
import binascii
import hashlib
import hmac
import json
import time
import math
import threading
from dataclasses import dataclass
from typing import Any, Optional, Tuple
from urllib.parse import urlparse

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa


class InvalidBearerToken(ValueError):
    """Token sai định dạng, không đáng tin cậy, hết hạn hoặc sai đối tượng nhận."""


@dataclass(frozen=True)
class VerifiedIdentity:
    subject: str
    issuer: str
    audience: Tuple[str, ...]
    expires_at: int
    workspace_id: Optional[str] = None
    email: Optional[str] = None

    @property
    def user_id(self) -> str:
        return self.subject


def _decode_segment(segment: str) -> bytes:
    try:
        encoded = (segment + "=" * (-len(segment) % 4)).encode("ascii")
        return base64.b64decode(encoded, altchars=b"-_", validate=True)
    except (ValueError, UnicodeEncodeError, binascii.Error) as exc:
        raise InvalidBearerToken("MALFORMED_TOKEN") from exc


def _numeric_date(value: Any, claim: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidBearerToken(f"INVALID_{claim.upper()}")
    number = float(value)
    if not math.isfinite(number):
        raise InvalidBearerToken(f"INVALID_{claim.upper()}")
    return number


def _reject_json_constant(value: str):
    raise InvalidBearerToken("MALFORMED_CLAIMS")


def verify_bearer_token(
    token: str,
    *,
    secret: str,
    issuer: str,
    audience: str,
) -> VerifiedIdentity:
    """Xác minh JWT HS256 cùng issuer, audience, subject và thời hạn."""
    if not all(isinstance(value, str) and value.strip() for value in (token, secret, issuer, audience)):
        raise InvalidBearerToken("VERIFIER_CONFIGURATION_MISSING")
    if len(token) > 16_384:
        raise InvalidBearerToken("TOKEN_TOO_LARGE")

    parts = token.split(".")
    if len(parts) != 3:
        raise InvalidBearerToken("MALFORMED_TOKEN")
    encoded_header, encoded_payload, encoded_signature = parts

    try:
        header = json.loads(_decode_segment(encoded_header), parse_constant=_reject_json_constant)
        claims = json.loads(_decode_segment(encoded_payload), parse_constant=_reject_json_constant)
        signature = _decode_segment(encoded_signature)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise InvalidBearerToken("MALFORMED_TOKEN") from exc
    if not isinstance(header, dict) or header.get("alg") != "HS256":
        raise InvalidBearerToken("UNSUPPORTED_ALGORITHM")
    if not isinstance(claims, dict):
        raise InvalidBearerToken("MALFORMED_CLAIMS")

    try:
        signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    except UnicodeEncodeError as exc:
        raise InvalidBearerToken("MALFORMED_TOKEN") from exc
    expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        raise InvalidBearerToken("INVALID_SIGNATURE")

    subject = claims.get("sub")
    token_issuer = claims.get("iss")
    token_audience = claims.get("aud")
    if not isinstance(subject, str) or not subject.strip():
        raise InvalidBearerToken("MISSING_SUBJECT")
    if token_issuer != issuer:
        raise InvalidBearerToken("INVALID_ISSUER")
    if isinstance(token_audience, str):
        audiences = (token_audience,)
    elif isinstance(token_audience, list) and all(isinstance(item, str) for item in token_audience):
        audiences = tuple(token_audience)
    else:
        raise InvalidBearerToken("INVALID_AUDIENCE")
    if audience not in audiences:
        raise InvalidBearerToken("INVALID_AUDIENCE")

    expires_at = _numeric_date(claims.get("exp"), "exp")
    now = time.time()
    if expires_at <= now:
        raise InvalidBearerToken("TOKEN_EXPIRED")
    if "nbf" in claims and _numeric_date(claims["nbf"], "nbf") > now:
        raise InvalidBearerToken("TOKEN_NOT_YET_VALID")

    workspace_id = claims.get("workspace_id")
    if workspace_id is not None and (
        not isinstance(workspace_id, str)
        or not workspace_id.strip()
        or workspace_id != workspace_id.strip()
        or len(workspace_id) > 36
    ):
        raise InvalidBearerToken("INVALID_WORKSPACE_ID")

    return VerifiedIdentity(
        subject=subject,
        issuer=token_issuer,
        audience=audiences,
        expires_at=int(expires_at),
        workspace_id=workspace_id,
    )


_ACCESS_JWKS_CACHE: dict[str, tuple[float, float, dict[str, rsa.RSAPublicKey]]] = {}
_ACCESS_JWKS_LOCK = threading.Lock()


def _access_public_keys(issuer: str, *, refresh: bool = False) -> dict[str, rsa.RSAPublicKey]:
    now = time.monotonic()
    with _ACCESS_JWKS_LOCK:
        cached = _ACCESS_JWKS_CACHE.get(issuer)
        if cached and now < cached[0] and (not refresh or now < cached[1]):
            return cached[2]
        try:
            response = httpx.get(f"{issuer}/cdn-cgi/access/certs", timeout=5.0)
            response.raise_for_status()
            jwks = response.json()
        except Exception as exc:
            raise InvalidBearerToken("ACCESS_JWKS_UNAVAILABLE") from exc
        if not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list):
            raise InvalidBearerToken("INVALID_ACCESS_JWKS")

        keys: dict[str, rsa.RSAPublicKey] = {}
        try:
            for item in jwks["keys"]:
                if not isinstance(item, dict) or item.get("kty") != "RSA":
                    continue
                if item.get("use", "sig") != "sig" or item.get("alg", "RS256") != "RS256":
                    continue
                kid, modulus, exponent = item.get("kid"), item.get("n"), item.get("e")
                if not all(isinstance(value, str) and value for value in (kid, modulus, exponent)):
                    continue
                n = int.from_bytes(_decode_segment(modulus), "big")
                e = int.from_bytes(_decode_segment(exponent), "big")
                if n.bit_length() < 2048:
                    continue
                keys[kid] = rsa.RSAPublicNumbers(e, n).public_key()
        except Exception as exc:
            raise InvalidBearerToken("INVALID_ACCESS_JWKS") from exc
        if not keys:
            raise InvalidBearerToken("INVALID_ACCESS_JWKS")
        _ACCESS_JWKS_CACHE[issuer] = (now + 300, now + 30, keys)
        return keys


def verify_cloudflare_access_jwt(
    token: str,
    *,
    issuer: str,
    audience: str,
) -> VerifiedIdentity:
    """Xác minh assertion RS256 của Cloudflare Access và danh tính email."""
    if not all(isinstance(value, str) and value.strip() for value in (token, issuer, audience)):
        raise InvalidBearerToken("VERIFIER_CONFIGURATION_MISSING")
    if len(token) > 16_384:
        raise InvalidBearerToken("TOKEN_TOO_LARGE")
    issuer = issuer.strip().rstrip("/")
    parsed_issuer = urlparse(issuer)
    if parsed_issuer.scheme != "https" or not parsed_issuer.netloc or parsed_issuer.path:
        raise InvalidBearerToken("INVALID_ISSUER_CONFIGURATION")

    parts = token.split(".")
    if len(parts) != 3:
        raise InvalidBearerToken("MALFORMED_TOKEN")
    encoded_header, encoded_payload, encoded_signature = parts
    try:
        header = json.loads(_decode_segment(encoded_header), parse_constant=_reject_json_constant)
        claims = json.loads(_decode_segment(encoded_payload), parse_constant=_reject_json_constant)
        signature = _decode_segment(encoded_signature)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise InvalidBearerToken("MALFORMED_TOKEN") from exc
    if not isinstance(header, dict) or header.get("alg") != "RS256":
        raise InvalidBearerToken("UNSUPPORTED_ALGORITHM")
    kid = header.get("kid")
    if not isinstance(kid, str) or not kid.strip():
        raise InvalidBearerToken("MISSING_KEY_ID")
    if not isinstance(claims, dict):
        raise InvalidBearerToken("MALFORMED_CLAIMS")

    keys = _access_public_keys(issuer)
    public_key = keys.get(kid)
    if public_key is None:
        keys = _access_public_keys(issuer, refresh=True)
        public_key = keys.get(kid)
    if public_key is None:
        raise InvalidBearerToken("UNKNOWN_KEY_ID")
    try:
        signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
        public_key.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
    except (InvalidSignature, UnicodeEncodeError, ValueError) as exc:
        raise InvalidBearerToken("INVALID_SIGNATURE") from exc

    subject = claims.get("sub")
    token_issuer = claims.get("iss")
    token_audience = claims.get("aud")
    if not isinstance(subject, str) or not subject.strip():
        raise InvalidBearerToken("MISSING_SUBJECT")
    if token_issuer != issuer:
        raise InvalidBearerToken("INVALID_ISSUER")
    if isinstance(token_audience, str):
        audiences = (token_audience,)
    elif isinstance(token_audience, list) and all(isinstance(item, str) for item in token_audience):
        audiences = tuple(token_audience)
    else:
        raise InvalidBearerToken("INVALID_AUDIENCE")
    if audience not in audiences:
        raise InvalidBearerToken("INVALID_AUDIENCE")

    expires_at = _numeric_date(claims.get("exp"), "exp")
    now = time.time()
    if expires_at <= now:
        raise InvalidBearerToken("TOKEN_EXPIRED")
    if "nbf" in claims and _numeric_date(claims["nbf"], "nbf") > now:
        raise InvalidBearerToken("TOKEN_NOT_YET_VALID")
    email = claims.get("email")
    if not isinstance(email, str) or not email.strip() or "@" not in email:
        raise InvalidBearerToken("MISSING_EMAIL")

    return VerifiedIdentity(
        subject=subject,
        issuer=token_issuer,
        audience=audiences,
        expires_at=int(expires_at),
        email=email.strip().lower(),
    )
