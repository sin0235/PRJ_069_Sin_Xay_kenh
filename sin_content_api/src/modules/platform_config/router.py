# Router API quan tri cau hinh LLM 9Router danh rieng cho Platform Owner (Gate 2)
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.auth.platform_auth import require_platform_owner
from src.modules.platform_config.contracts import (
    PlatformLLMConfigOut, PlatformLLMConfigUpdate,
    PlatformLLMProbeRequest, PlatformLLMProbeResult,
    PlatformLLMPublicStatus
)
from src.modules.platform_config.service import platform_config_service

router = APIRouter(prefix="/v1/platform/llm-config", tags=["Platform LLM Gateway Admin"])

@router.get("", response_model=PlatformLLMConfigOut)
def get_llm_config(
    db: Session = Depends(get_db),
    owner_user_id: str = Depends(require_platform_owner)
):
    """
    Lay thong tin cau hinh cong LLM trung tam.
    Yeu cau xac thuc danh tinh Platform Owner. Tuyet doi khong tra ve API Key dang ro.
    """
    return platform_config_service.get_config_out(db)

@router.put("", response_model=PlatformLLMConfigOut)
def update_llm_config(
    payload: PlatformLLMConfigUpdate,
    db: Session = Depends(get_db),
    owner_user_id: str = Depends(require_platform_owner)
):
    """
    Cap nhat cau hinh cong LLM trung tam.
    Chi Platform Owner duoc phep thay doi. API key moi se duoc ma hoa an toan truoc khi luu.
    Neu new_api_key de trong hoac null, he thong giu nguyen khoa cu da luu.
    """
    return platform_config_service.update_config(db, owner_user_id, payload)

@router.post("/probe", response_model=PlatformLLMProbeResult)
def probe_llm_gateway(
    payload: PlatformLLMProbeRequest,
    db: Session = Depends(get_db),
    owner_user_id: str = Depends(require_platform_owner)
):
    """
    Kiem tra ket noi den cong 9Router ma khong lam tieu hao chi phi token.
    Chi Platform Owner duoc phep thao tac.
    """
    return platform_config_service.probe_gateway(db, payload)

@router.get("/public-status", response_model=PlatformLLMPublicStatus)
def get_public_llm_status(
    db: Session = Depends(get_db)
):
    """
    Xem trang thai toi gian cua cong LLM (danh cho giao dien nguoi dung thong thuong).
    Khong yeu cau quyen Owner, khong lo bat ky thong so ky thuat nhay cam nao.
    """
    return platform_config_service.get_public_status(db)
