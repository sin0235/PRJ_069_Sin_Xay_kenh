"""Kiểm thử cho cổng chất lượng cong_chat_luong.py (Task 12).

Bao gồm:
- test_gate_khong_co_canh_khoi: không có cảnh khối trả về [] mà không mở trình duyệt.
- test_gate_bat_chu_mau_tieng_anh: kiểm tra hàm thuần scan_english và bắt chữ Workspace không cần mở trình duyệt.
- test_scan_url_ngoai: kiểm tra hàm thuần scan_urls và bắt URL từ xa không cần mở trình duyệt.
- test_gate_bat_chu_tran_mep: kiểm tra chữ tràn mép ở khung hình 9:16 (1 lượt render trình duyệt).
- test_gate_dat_voi_canh_binh_thuong: kiểm tra cảnh KINETIC_TITLE ngắn bình thường ở 16:9 đạt chuẩn [] (1 lượt render).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "sin_content_api") not in sys.path:
    sys.path.insert(0, str(ROOT / "sin_content_api"))

from ha_tang.hyperframes import cong_chat_luong
from src.modules.tao_video_noi_dung import planner


def test_gate_khong_co_canh_khoi(monkeypatch):
    """Không có cảnh khối nào thì trả về [] ngay lập tức, không gọi trình duyệt."""
    def _fail_call(*args, **kwargs):
        raise AssertionError("Không được gọi tiến trình ngoài khi storyboard không có cảnh khối")

    monkeypatch.setattr("subprocess.run", _fail_call)

    shot = planner.StoryboardShot.model_construct(
        shot_id="shot_flow_01",
        shot_kind="FLOW_ORIGAMI",
        narration="Lời đọc cho cảnh Flow Origami",
        duration_seconds=5,
        prompt="Mô tả prompt",
        scene="Mô tả cảnh",
    )
    storyboard = planner.Storyboard.model_construct(
        title="Dự án chỉ có cảnh Flow",
        narration="Lời đọc cho toàn bộ video",
        continuity_anchor="Mỏ neo đảm bảo tính liên tục của nội dung",
        shots=[shot],
    )
    problems = cong_chat_luong.gate_storyboard(storyboard, aspect="16:9")
    assert problems == []


def test_gate_bat_chu_mau_tieng_anh(monkeypatch, tmp_path):
    """Kiểm tra hàm scan_english và cơ chế phát hiện từ mẫu tiếng Anh rò rỉ mà không mở trình duyệt."""
    # 1. Kiểm tra trực tiếp hàm thuần scan_english
    sample_html = """
    <div class="fr-stage">
        <span class="fr-kicker">Workspace</span>
        <div class="fr-label">Brand A</div>
    </div>
    <script>
        const status = "Workspace";
    </script>
    """
    detected = cong_chat_luong.scan_english(sample_html)
    assert "Workspace" in detected
    assert "Brand A" in detected

    clean_vietnamese_html = """
    <div class="content">
        <h1>Một nguồn sự thật duy nhất</h1>
        <p>Báo cáo tự động hóa cho doanh nghiệp</p>
    </div>
    <script>
        const title = "Một nguồn sự thật";
    </script>
    """
    assert cong_chat_luong.scan_english(clean_vietnamese_html) == []

    # 2. Stub kiểm tra trình duyệt để chạy gate_storyboard không cần mở Chrome
    monkeypatch.setattr(cong_chat_luong, "run_project_check", lambda proj: {})
    monkeypatch.setattr(cong_chat_luong, "capture_snapshots", lambda proj, out, at: [])

    shot = planner.StoryboardShot.model_construct(
        shot_id="shot_en_test",
        shot_kind="UI_SIM",
        ui_scene=planner.UiScene.model_construct(
            layout="KINETIC_TITLE",
            diagram=planner.DiagramSpec.model_construct(title="Một nguồn sự thật", tag="sự thật"),
            messages=[],
        ),
        narration="Lời đọc kiểm tra",
        duration_seconds=5,
        prompt="prompt",
        scene="scene",
    )
    storyboard = planner.Storyboard.model_construct(
        title="Storyboard chứa từ mẫu tiếng Anh",
        narration="Lời đọc",
        continuity_anchor="Mỏ neo tính liên tục",
        shots=[shot],
    )

    orig_build = cong_chat_luong.hf_project.build_project

    def _build_with_workspace(out, shots, voice_wav, words, transitions=False, aspect_ratio="16:9"):
        info = orig_build(out, shots, voice_wav, words, transitions=transitions, aspect_ratio=aspect_ratio)
        comp_file = Path(out) / "compositions" / "s01.html"
        comp_file.write_text(comp_file.read_text(encoding="utf-8") + "<div>Workspace</div>", encoding="utf-8")
        return info

    monkeypatch.setattr(cong_chat_luong.hf_project, "build_project", _build_with_workspace)

    problems = cong_chat_luong.gate_storyboard(storyboard, aspect="16:9", work_dir=tmp_path / "work")
    assert any("shot_en_test: ENGLISH_SAMPLE_TEXT: Workspace" in p for p in problems)


def test_scan_url_ngoai(monkeypatch, tmp_path):
    """Kiểm tra hàm scan_urls và cơ chế phát hiện URL từ xa mà không mở trình duyệt."""
    sample_external = '<script src="https://cdn.example.com/malicious.js"></script>'
    urls = cong_chat_luong.scan_urls(sample_external)
    assert "https://cdn.example.com/malicious.js" in urls

    sample_clean = '<script src="assets/vendor/gsap.min.js"></script>'
    assert cong_chat_luong.scan_urls(sample_clean) == []

    monkeypatch.setattr(cong_chat_luong, "run_project_check", lambda proj: {})
    monkeypatch.setattr(cong_chat_luong, "capture_snapshots", lambda proj, out, at: [])

    shot = planner.StoryboardShot.model_construct(
        shot_id="shot_url_test",
        shot_kind="UI_SIM",
        ui_scene=planner.UiScene.model_construct(
            layout="KINETIC_TITLE",
            diagram=planner.DiagramSpec.model_construct(title="Một nguồn sự thật", tag="sự thật"),
            messages=[],
        ),
        narration="Lời đọc kiểm tra",
        duration_seconds=5,
        prompt="prompt",
        scene="scene",
    )
    storyboard = planner.Storyboard.model_construct(
        title="Storyboard chứa URL ngoài",
        narration="Lời đọc",
        continuity_anchor="Mỏ neo tính liên tục",
        shots=[shot],
    )

    orig_build = cong_chat_luong.hf_project.build_project

    def _build_with_url(out, shots, voice_wav, words, transitions=False, aspect_ratio="16:9"):
        info = orig_build(out, shots, voice_wav, words, transitions=transitions, aspect_ratio=aspect_ratio)
        comp_file = Path(out) / "compositions" / "s01.html"
        comp_file.write_text(comp_file.read_text(encoding="utf-8") + sample_external, encoding="utf-8")
        return info

    monkeypatch.setattr(cong_chat_luong.hf_project, "build_project", _build_with_url)

    problems = cong_chat_luong.gate_storyboard(storyboard, aspect="16:9", work_dir=tmp_path / "work")
    assert any("shot_url_test: EXTERNAL_URL: https://cdn.example.com/malicious.js" in p for p in problems)


@pytest.mark.browser
def test_gate_bat_chu_tran_mep(tmp_path):
    """Kiểm tra chữ tràn mép trong khung 9:16 bằng 1 lượt render trình duyệt duy nhất."""
    title_60 = "Nhiều doanh nghiệp chuyển đổi phương thức hoạt động"
    scene_60 = planner.UiScene.model_construct(
        layout="MARK_PHRASE",
        diagram=planner.DiagramSpec.model_construct(
            title=title_60,
            tag="phương thức hoạt động",
            caption="Không ai sai",
        ),
        messages=[],
    )
    shot_60 = planner.StoryboardShot.model_construct(
        shot_id="shot_60char",
        shot_kind="UI_SIM",
        ui_scene=scene_60,
        narration="Lời đọc cho cảnh tiêu đề dài vừa phải",
        duration_seconds=5,
        prompt="prompt",
        scene="scene",
    )

    absurd_title = (
        "Một_câu_tiêu_đề_cực_kỳ_dài_vượt_quá_giới_hạn_một_trăm_hai_mươi_ký_tự_để_"
        "kiểm_tra_chữ_tràn_mép_khung_hình_dọc_chín_mười_sáu_hoàn_toàn"
    )
    scene_absurd = planner.UiScene.model_construct(
        layout="MARK_PHRASE",
        diagram=planner.DiagramSpec.model_construct(
            title=absurd_title,
            tag=absurd_title,
            caption="Phụ đề",
        ),
        messages=[],
    )
    shot_absurd = planner.StoryboardShot.model_construct(
        shot_id="shot_120char",
        shot_kind="UI_SIM",
        ui_scene=scene_absurd,
        narration="Lời đọc cho cảnh tiêu đề cực dài cố tình vượt ngưỡng",
        duration_seconds=5,
        prompt="prompt",
        scene="scene",
    )

    storyboard = planner.Storyboard.model_construct(
        title="Kiểm tra phát hiện chữ tràn mép",
        narration="Lời đọc toàn bộ storyboard",
        continuity_anchor="Mỏ neo tính liên tục của câu chuyện",
        shots=[shot_60, shot_absurd],
    )

    problems = cong_chat_luong.gate_storyboard(storyboard, aspect="9:16", work_dir=tmp_path / "work")
    assert isinstance(problems, list)
    assert any("shot_120char: TEXT_TOUCHES_EDGE" in p for p in problems)


@pytest.mark.browser
def test_gate_dat_voi_canh_binh_thuong(tmp_path):
    """Cảnh KINETIC_TITLE ngắn bình thường trong khung 16:9 đạt chuẩn cổng chất lượng (1 lượt render)."""
    scene_normal = planner.UiScene(
        layout="KINETIC_TITLE",
        diagram=planner.DiagramSpec(title="Một nguồn sự thật", tag="sự thật"),
    )
    shot_normal = planner.StoryboardShot.model_construct(
        shot_id="shot_normal",
        shot_kind="UI_SIM",
        ui_scene=scene_normal,
        narration="Lời đọc cho cảnh tiêu đề bình thường",
        duration_seconds=4,
        prompt="prompt",
        scene="scene",
    )
    storyboard = planner.Storyboard.model_construct(
        title="Storyboard cảnh bình thường",
        narration="Lời đọc",
        continuity_anchor="Mỏ neo tính liên tục của câu chuyện",
        shots=[shot_normal],
    )

    problems = cong_chat_luong.gate_storyboard(storyboard, aspect="16:9", work_dir=tmp_path / "work")
    assert problems == []
