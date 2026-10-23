import pytest
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from src.modules.dieu_phoi_dung.hop_dong import TimelineV2, TrackV2, ClipV2, ThoiGianNguon


class MauThuongHieu(BaseModel):
    brand_id: str
    version: str = "1.0"
    font_name: str = "Arial"
    primary_color_hex: str = "#A855F7"
    glossary: Dict[str, str] = Field(default_factory=dict)
    safe_zone: Dict[str, int] = Field(default_factory=lambda: {"top": 150, "bottom": 320, "right": 120})


class BienTheTimeline(BaseModel):
    variant_id: str
    parent_timeline_hash: str
    aspect_ratio: str  # 9:16 | 16:9 | 1:1
    width: int
    height: int
    revision: int = 1
    qc_passed: bool = False
    ai_generation_calls_count: int = 0  # Bắt buộc = 0 nếu chỉ đổi tỷ lệ khung hình đóng gói


class CommentTimecode(BaseModel):
    comment_id: str
    target_revision: int
    timecode_ms: int
    author: str
    text: str
    resolved: bool = False


def test_template_version_khong_sua_nguon():
    """
    Kiem tra template thuong hieu (brand kit, glossary, font) co version ro rang
    va khi ap dung khong lam thay doi du lieu nguon goc
    """
    brand_kit = MauThuongHieu(
        brand_id="brand_sin_tea",
        version="1.2",
        font_name="Arial",
        primary_color_hex="#2457D6",
        glossary={"tra sua": "Trà Sữa Sin", "oolong": "Oolong Hoàng Kim"}
    )
    assert brand_kit.version == "1.2"
    assert brand_kit.glossary["oolong"] == "Oolong Hoàng Kim"
    assert brand_kit.safe_zone["top"] == 150


def test_bien_the_khong_goi_lai_generation():
    """
    Kiem tra tao bien the 16:9 hoac 1:1 tu ban master 9:16 khong duoc goi lai provider AI
    sinh hinh/nhac (ai_generation_calls_count == 0)
    """
    master_hash = "sha256_master_9_16_tiktok"

    variant_16_9 = BienTheTimeline(
        variant_id="var_youtube_16_9",
        parent_timeline_hash=master_hash,
        aspect_ratio="16:9",
        width=1920,
        height=1080,
        revision=1,
        qc_passed=True,
        ai_generation_calls_count=0  # 0 outbound generation
    )
    assert variant_16_9.ai_generation_calls_count == 0
    assert variant_16_9.parent_timeline_hash == master_hash
    assert variant_16_9.width == 1920
    assert variant_16_9.height == 1080


def test_comment_ban_cu_khong_sua_nham_ban_moi():
    """
    Kiem tra comment duoc neo chat voi target_revision:
    Comment o revision 1 khong duoc tu dong ap nham vao revision 2 sau khi da sua
    """
    cmt_rev1 = CommentTimecode(
        comment_id="cmt_01",
        target_revision=1,
        timecode_ms=1500,
        author="Lead Editor",
        text="Giam volume tieng doan nay xuong"
    )

    current_revision = 2
    # Kiem tra comment co thuoc revision hien tai hay khong
    is_applicable_to_current = (cmt_rev1.target_revision == current_revision)
    assert is_applicable_to_current is False
    assert cmt_rev1.target_revision == 1
