import json
import math
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from src.modules.tao_video_noi_dung import render_engines
from src.modules.tao_video_noi_dung.planner import UiScene


def checklist_scene():
    return UiScene.model_validate({"layout": "CHECKLIST", "diagram": {
        "title": "Ba bước", "simulated": False, "steps": ["Đo dữ liệu", "Chọn điểm", "Kiểm tra"],
        "camera_motion": "PARALLAX_PASS",
        "on": {"c0": "Đo dữ liệu", "c1": "Chọn điểm", "c2": "Kiểm tra"},
    }})


def test_props_giu_du_lieu_su_kien_va_hop_dong_v1():
    scene = checklist_scene()
    narration = "Đo dữ liệu, chọn điểm, kiểm tra."
    props = render_engines.native_remotion_props(
        scene, 5, "9:16", narration, [0.2, 0.4, 0.5, 0.8, 0.9, 1.0, 1.1]
    )

    assert props["schemaVersion"] == 1
    assert props["diagram"] == render_engines.diagram_payload(scene, narration, 5, [0.2, 0.4, 0.5, 0.8, 0.9, 1.0, 1.1])
    assert props["diagram"]["simulated"] is False
    assert props["diagram"]["camera_motion"] == "PARALLAX_PASS"
    assert props["fps"] == 30 and props["durationInFrames"] == 150
    assert (props["width"], props["height"]) == (1080, 1920)
    assert props["theme"] == {
        "background": "#0B0F17", "surface": "#1C2A40", "ink": "#F2EEE6", "accent": "#D9B26A"
    }
    assert props["assets"] == {
        "font": "phong_chu/be_vietnam_pro_dam.ttf", "logo": "thuong_hieu/logo_ngang_mau.png"
    }


@pytest.mark.parametrize("aspect,dimensions", [("9:16", (1080, 1920)), ("16:9", (1920, 1080))])
def test_props_dung_kich_thuoc_theo_ti_le(aspect, dimensions):
    props = render_engines.native_remotion_props(checklist_scene(), 5, aspect, "Đo dữ liệu, chọn điểm, kiểm tra.")
    assert (props["width"], props["height"]) == dimensions


@pytest.mark.parametrize("scene", [
    UiScene.model_validate({"layout": "KPI_CARDS", "diagram": {
        "title": "Kết quả", "cards": [{"title": "Doanh thu", "label": "+18%", "value": "1,2 tỷ"},
                                         {"title": "Thời gian", "label": "-20%", "value": "8 phút"}],
        "on": {"k0": "doanh thu", "k1": "thời gian"},
    }}),
    UiScene.model_validate({"layout": "BEFORE_AFTER", "diagram": {
        "title": "Đơn hàng", "simulated": False,
        "docs": [{"title": "Trước", "label": "Đơn", "value": "100"}, {"title": "Sau", "label": "Đơn", "value": "60"}],
        "diff_label": "Giảm 40", "on": {"before": "trước", "after": "sau", "delta": "giảm 40"},
    }}),
])
def test_props_ho_tro_ba_layout_native(scene):
    narration = "Doanh thu, thời gian. Trước, sau, giảm 40."
    # Resolve đúng các event neo của từng layout qua dữ liệu đã được Pydantic kiểm tra.
    if scene.layout == "BEFORE_AFTER":
        narration = "Trước, sau, giảm 40."
    props = render_engines.native_remotion_props(scene, 4, "16:9", narration)
    assert props["diagram"]["kind"] == scene.layout


@pytest.mark.parametrize("seconds", [0, -1, math.nan, math.inf, -math.inf])
def test_props_tu_choi_thoi_luong_khong_hop_le(seconds):
    with pytest.raises(ValueError):
        render_engines.native_remotion_props(checklist_scene(), seconds, "9:16", "Đo dữ liệu, chọn điểm, kiểm tra.")


@pytest.mark.parametrize("word_times", [[0, math.nan, 1, 2, 3, 4, 5], [0, 0.5, 0.4, 1, 2, 3, 4], [0, 1]])
def test_props_tu_choi_word_times_sai(word_times):
    with pytest.raises(ValueError, match="WORD_TIMES"):
        render_engines.native_remotion_props(checklist_scene(), 5, "9:16", "Đo dữ liệu, chọn điểm, kiểm tra.", word_times)


def test_event_frame_lam_tron_half_up_va_chan_bien():
    assert render_engines.native_event_frame(-0.2, 38) == 0
    assert render_engines.native_event_frame(1.25, 38) == 37
    assert render_engines.native_event_frame(0.05, 38) == 2


def test_duration_1_25_giay_lam_tron_thanh_38_frame(monkeypatch):
    monkeypatch.setattr(render_engines, "diagram_payload", lambda *_args: {"kind": "CHECKLIST", "t": {"c0": 1.25}})
    props = render_engines.native_remotion_props(checklist_scene(), 1.25, "9:16", "lời đọc")
    assert props["durationInFrames"] == 38


def test_native_chi_bat_cho_ba_layout_va_dung_opt_in():
    scene = checklist_scene()
    assert render_engines.native_remotion_enabled(scene, {"render_engine": "remotion", "remotion_native": True})
    assert not render_engines.native_remotion_enabled(scene, {"render_engine": "remotion"})
    assert not render_engines.native_remotion_enabled(scene, {"render_engine": "playwright", "remotion_native": True})
    unsupported = UiScene(layout="CHAT", messages=[
        {"role": "customer", "text": "Cần dữ liệu.", "at_s": 0},
        {"role": "ai", "text": "Đo dữ liệu.", "at_s": 1},
    ])
    assert not render_engines.native_remotion_enabled(unsupported, {"render_engine": "remotion", "remotion_native": True})


def test_native_render_goi_composition_va_props_json(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "engines" / "remotion"
    cli = root / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"
    cli.parent.mkdir(parents=True)
    cli.write_text("", encoding="utf-8")
    for asset in render_engines.NATIVE_REMOTION_ASSETS.values():
        asset_path = root / "public" / asset
        asset_path.parent.mkdir(parents=True, exist_ok=True)
        asset_path.write_bytes(b"asset")
    monkeypatch.setattr(render_engines, "engines_dir", lambda: tmp_path / "engines")
    monkeypatch.setattr(render_engines, "_node", lambda: "node")
    monkeypatch.setattr(render_engines, "_chrome", lambda: None)
    monkeypatch.setattr(render_engines, "_remotion_bundle", lambda *_args: root / "bundle")
    command_seen = {}

    def run(command, *_args):
        command_seen["command"] = command
        props_file = next(arg.split("=", 1)[1] for arg in command if arg.startswith("--props="))
        assert Path(props_file).is_absolute()
        assert Path(command[5]).is_absolute()
        command_seen["props"] = json.loads(Path(props_file).read_text(encoding="utf-8"))

    monkeypatch.setattr(render_engines, "_run", run)
    monkeypatch.setattr(render_engines, "_normalize", lambda *_args: {"width": 1080, "height": 1920})
    result = render_engines.render_scene(
        checklist_scene(), {"render_engine": "remotion", "remotion_native": True}, 5, "9:16", Path("ket_qua/clip.mp4"),
        narration="Đo dữ liệu, chọn điểm, kiểm tra.",
    )

    assert "CanhTrucTiep" in command_seen["command"]
    assert command_seen["props"]["schemaVersion"] == 1
    assert "html" not in command_seen["props"]
    assert result["render_engine"] == "remotion" and result["render_variant"] == "native"
    assert result["renderer_revision"] and result["render_fingerprint"]


def test_doc_log_renderer_bang_utf8(monkeypatch, tmp_path):
    from types import SimpleNamespace
    captured = {}

    def run(*_args, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(returncode=0, stdout="Đã dựng cảnh", stderr="")

    monkeypatch.setattr(render_engines.subprocess, "run", run)
    render_engines._run(["node", "canh"], tmp_path)
    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"


def test_native_alpha_bi_tu_choi_truoc_fallback(monkeypatch, tmp_path):
    called = []
    monkeypatch.setattr(render_engines, "render_ui_scene", lambda *_args, **_kwargs: called.append(True))
    with pytest.raises(ValueError, match="ALPHA"):
        render_engines.render_scene(
            checklist_scene(), {"render_engine": "remotion", "remotion_native": True}, 2, "9:16",
            tmp_path / "clip.mov", narration="Đo dữ liệu, chọn điểm, kiểm tra.", transparent_background=True,
        )
    assert called == []


def test_engine_runtime_error_co_fallback_va_loi_du_lieu_khong_fallback(monkeypatch, tmp_path):
    scene = checklist_scene()
    monkeypatch.setitem(render_engines.BACKENDS, "remotion", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("engine timeout")))
    monkeypatch.setattr(render_engines, "render_ui_scene", lambda *_args, **_kwargs: {"width": 1080, "height": 1920})
    result = render_engines.render_scene(
        scene, {"render_engine": "remotion", "remotion_native": True}, 5, "9:16", tmp_path / "clip.mp4",
        narration="Đo dữ liệu, chọn điểm, kiểm tra.",
    )
    assert (result["render_engine"], result["render_variant"]) == ("playwright", "fallback")

    with pytest.raises(ValueError, match="DIAGRAM_PHRASE_NOT_IN_NARRATION"):
        render_engines.render_scene(
            scene, {"render_engine": "remotion", "remotion_native": True}, 5, "9:16", tmp_path / "clip.mp4",
            narration="Lời đọc không có sự kiện neo.",
        )


def test_fingerprint_thay_doi_khi_lockfile_hoac_public_asset_doi(monkeypatch, tmp_path):
    root = tmp_path / "engines" / "remotion"
    (root / "src").mkdir(parents=True)
    (root / "src" / "Root.jsx").write_text("root", encoding="utf-8")
    (root / "public" / "phong_chu").mkdir(parents=True)
    (root / "public" / "phong_chu" / "be_vietnam_pro_dam.ttf").write_bytes(b"font-a")
    (root / "package.json").write_text("{}", encoding="utf-8")
    (root / "package-lock.json").write_text("lock-a", encoding="utf-8")
    monkeypatch.setattr(render_engines, "engines_dir", lambda: tmp_path / "engines")
    first = render_engines.native_remotion_fingerprint(checklist_scene(), 5, "9:16", "Đo dữ liệu, chọn điểm, kiểm tra.")
    (root / "package-lock.json").write_text("lock-b", encoding="utf-8")
    second = render_engines.native_remotion_fingerprint(checklist_scene(), 5, "9:16", "Đo dữ liệu, chọn điểm, kiểm tra.")
    (root / "public" / "phong_chu" / "be_vietnam_pro_dam.ttf").write_bytes(b"font-b")
    third = render_engines.native_remotion_fingerprint(checklist_scene(), 5, "9:16", "Đo dữ liệu, chọn điểm, kiểm tra.")
    assert len({first, second, third}) == 3


def test_bundle_cache_lockfile_public_va_staging_dong_thoi(monkeypatch, tmp_path):
    root = tmp_path / "remotion"
    (root / "src").mkdir(parents=True)
    (root / "src" / "index.js").write_text("entry", encoding="utf-8")
    (root / "public").mkdir()
    (root / "public" / "logo.png").write_bytes(b"logo-a")
    (root / "package.json").write_text("{}", encoding="utf-8")
    (root / "package-lock.json").write_text("lock-a", encoding="utf-8")
    monkeypatch.setenv("PRJ069_ENGINES_CACHE", str(tmp_path / "cache"))
    barrier = threading.Barrier(2)
    call_lock = threading.Lock()
    call_count = 0
    staging_paths = []

    def bundle(command, *_args):
        nonlocal call_count
        staging = Path(next(arg.split("=", 1)[1] for arg in command if arg.startswith("--out-dir=")))
        staging_paths.append(staging)
        with call_lock:
            call_count += 1
            concurrent = call_count <= 2
        if concurrent:
            barrier.wait(timeout=5)
        staging.mkdir()
        (staging / "index.html").write_text("bundle", encoding="utf-8")

    monkeypatch.setattr(render_engines, "_run", bundle)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: render_engines._remotion_bundle(root, "node", Path("cli")), range(2)))
    assert results[0] == results[1] and (results[0] / "index.html").is_file()
    assert len(set(staging_paths)) == 2

    (root / "package-lock.json").write_text("lock-b", encoding="utf-8")
    assert render_engines._remotion_bundle(root, "node", Path("cli")) != results[0]
def test_native_khong_ho_tro_phai_ton_trong_tat_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("CONTENT_VIDEO_RENDER_FALLBACK", "0")
    monkeypatch.setattr(render_engines, "render_ui_scene", lambda *_args, **_kwargs: {"render_engine": "playwright"})
    with pytest.raises(render_engines.EngineUnavailable, match="UNSUPPORTED"):
        render_engines.render_scene(checklist_scene(), {"render_engine": "remotion", "remotion_native": True},
                                    21, "9:16", tmp_path / "khong_duoc_du_phong.mp4",
                                    narration="Đo dữ liệu, chọn điểm, kiểm tra.")

