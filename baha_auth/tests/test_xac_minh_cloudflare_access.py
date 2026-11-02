"""Kiểm thử xác minh assertion Access bằng khóa công khai giả lập."""

import base64
import json
import time

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
import httpx

from baha_auth.src import xac_minh_danh_tinh


ISSUER = "https://unit-test.cloudflareaccess.com"
AUDIENCE = "prj069-test-audience"
KID = "unit-test-key"


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _token(private_key, *, claims=None, kid=KID, signature_key=None):
    payload = claims or {
        "sub": "identity-1",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "exp": int(time.time()) + 300,
        "email": " Founder@Example.com ",
    }
    header = _b64url(json.dumps({"alg": "RS256", "kid": kid}, separators=(",", ":")).encode())
    body = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header}.{body}".encode("ascii")
    signer = signature_key or private_key
    signature = signer.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{header}.{body}.{_b64url(signature)}"


def _jwks(private_key, kid=KID):
    numbers = private_key.public_key().public_numbers()
    def integer(value):
        return value.to_bytes((value.bit_length() + 7) // 8, "big")
    return {"keys": [{"kty": "RSA", "use": "sig", "alg": "RS256", "kid": kid,
                      "n": _b64url(integer(numbers.n)), "e": _b64url(integer(numbers.e))}]}


class _Response:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self.data


def _install_jwks(monkeypatch, private_key, kid=KID):
    xac_minh_danh_tinh._ACCESS_JWKS_CACHE.pop(ISSUER, None)
    monkeypatch.setattr(httpx, "get", lambda *_args, **_kwargs: _Response(_jwks(private_key, kid)))


def _verify(token):
    verifier = getattr(xac_minh_danh_tinh, "verify_cloudflare_access_jwt", None)
    assert callable(verifier), "API chưa xác minh Cloudflare Access JWT"
    return verifier(token, issuer=ISSUER, audience=AUDIENCE)


def test_access_assertion_ky_hop_le_tra_email_da_chuan_hoa(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    _install_jwks(monkeypatch, private_key)

    identity = _verify(_token(private_key))

    assert identity.subject == "identity-1"
    assert identity.email == "founder@example.com"
    assert identity.issuer == ISSUER
    assert identity.audience == (AUDIENCE,)


@pytest.mark.parametrize(
    ("claims", "token_kid", "signing_key", "reason"),
    [
        ({"sub": "u", "iss": ISSUER, "aud": AUDIENCE, "exp": int(time.time()) + 60, "email": "u@example.com"}, KID, None, "INVALID_SIGNATURE"),
        ({"sub": "u", "iss": "https://wrong.example", "aud": AUDIENCE, "exp": int(time.time()) + 60, "email": "u@example.com"}, KID, "same", "INVALID_ISSUER"),
        ({"sub": "u", "iss": ISSUER, "aud": "wrong", "exp": int(time.time()) + 60, "email": "u@example.com"}, KID, "same", "INVALID_AUDIENCE"),
        ({"sub": "u", "iss": ISSUER, "aud": AUDIENCE, "exp": int(time.time()) - 60, "email": "u@example.com"}, KID, "same", "TOKEN_EXPIRED"),
        ({"sub": "u", "iss": ISSUER, "aud": AUDIENCE, "exp": int(time.time()) + 60}, KID, "same", "MISSING_EMAIL"),
    ],
)
def test_access_assertion_sai_claim_hoac_chu_ky_bi_tu_choi(monkeypatch, claims, token_kid, signing_key, reason):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    _install_jwks(monkeypatch, private_key)
    signer = private_key if signing_key == "same" else signing_key
    if signer is None:
        signer = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    with pytest.raises(xac_minh_danh_tinh.InvalidBearerToken, match=reason):
        _verify(_token(private_key, claims=claims, kid=token_kid, signature_key=signer))


def test_access_assertion_kid_khong_co_trong_jwks_bi_tu_choi(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    _install_jwks(monkeypatch, private_key)

    with pytest.raises(xac_minh_danh_tinh.InvalidBearerToken, match="UNKNOWN_KEY_ID"):
        _verify(_token(private_key, kid="unknown-key"))
