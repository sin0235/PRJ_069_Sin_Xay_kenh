import time

import pytest

from src.auth.mat_khau_noi_bo import (
    create_session_token,
    hash_password,
    verify_password,
    verify_session_token,
)


def test_mat_khau_dung_duoc_xac_minh_va_sai_bi_tu_choi():
    encoded = hash_password("mat-khau-mau-dai-va-rieng")

    assert verify_password("mat-khau-mau-dai-va-rieng", encoded)
    assert not verify_password("mat-khau-khac", encoded)


def test_phien_dang_nhap_giu_dung_workspace_va_tu_choi_token_sai():
    token = create_session_token(
        "user-founder",
        "workspace-prj069",
        secret="secret-mau-chi-dung-trong-test",
        issuer="issuer-test",
        audience="audience-test",
        now=1_900_000_000,
    )

    identity = verify_session_token(
        token,
        secret="secret-mau-chi-dung-trong-test",
        issuer="issuer-test",
        audience="audience-test",
        now=1_900_000_001,
    )
    assert identity.user_id == "user-founder"
    assert identity.workspace_id == "workspace-prj069"
    with pytest.raises(ValueError):
        verify_session_token(
            token + "x",
            secret="secret-mau-chi-dung-trong-test",
            issuer="issuer-test",
            audience="audience-test",
            now=1_900_000_001,
        )


def test_phien_dang_nhap_het_han_sau_tam_tieng():
    token = create_session_token(
        "user-founder",
        "workspace-prj069",
        secret="secret-mau-chi-dung-trong-test",
        issuer="issuer-test",
        audience="audience-test",
        now=1_900_000_000,
        lifetime_seconds=10,
    )

    with pytest.raises(ValueError):
        verify_session_token(
            token,
            secret="secret-mau-chi-dung-trong-test",
            issuer="issuer-test",
            audience="audience-test",
            now=1_900_000_011,
        )


def test_lifetime_mac_dinh_khong_vuot_qua_tam_tieng():
    token = create_session_token(
        "user-founder",
        "workspace-prj069",
        secret="secret-mau-chi-dung-trong-test",
        issuer="issuer-test",
        audience="audience-test",
        now=int(time.time()),
    )
    identity = verify_session_token(
        token,
        secret="secret-mau-chi-dung-trong-test",
        issuer="issuer-test",
        audience="audience-test",
    )
    assert identity.expires_at - int(time.time()) <= 8 * 60 * 60
