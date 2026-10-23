"""Xác minh bearer token do nhà cung cấp bên ngoài phát hành; không tạo token."""

import base64
import binascii
import hashlib
import hmac
import json
import time
import math
from dataclasses import dataclass
from typing import Any, Optional, Tuple


class InvalidBearerToken(ValueError):
    """Token sai định dạng, không đáng tin cậy, hết hạn hoặc sai đối tượng nhận."""


@dataclass(frozen=True)
class VerifiedIdentity:
    subject: str
    issuer: str
    audience: Tuple[str, ...]
    expires_at: int
    workspace_id: Optional[str] = None

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
