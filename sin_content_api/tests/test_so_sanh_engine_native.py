import json
import os
import sys

from scripts import so_sanh_engine


def test_import_va_chay_so_sanh_khong_doi_cau_hinh_chung(monkeypatch, tmp_path):
    import importlib

    monkeypatch.setenv("CONTENT_VIDEO_RENDER_FALLBACK", "1")
    importlib.reload(so_sanh_engine)
    assert os.environ["CONTENT_VIDEO_RENDER_FALLBACK"] == "1"
    monkeypatch.setattr(sys, "argv", ["so_sanh_engine.py", "--ra", str(tmp_path), "--engines", "remotion"])

    def fail(*_args, **_kwargs):
        assert os.environ["CONTENT_VIDEO_RENDER_FALLBACK"] == "0"
        raise RuntimeError("Lỗi thử nghiệm")

    monkeypatch.setattr(so_sanh_engine, "render_scene", fail)
    assert so_sanh_engine.main() == 1
    assert os.environ["CONTENT_VIDEO_RENDER_FALLBACK"] == "1"


def test_so_sanh_native_nhan_fixture_va_ghi_engine_that(monkeypatch, tmp_path):
    fixture = tmp_path / "canh.json"
    fixture.write_text(json.dumps({
        "scene": {"layout": "CHECKLIST", "diagram": {
            "title": "Ba bước", "steps": ["Đọc dữ liệu", "Đối chiếu", "Chốt"],
            "on": {"c0": "Đọc dữ liệu", "c1": "Đối chiếu", "c2": "Chốt"},
        }},
        "narration": "Đọc dữ liệu rồi Đối chiếu và Chốt", "word_times": [0, .2, .4, .7, 1, 1.2, 1.4, 1.6],
    }, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "ket_qua"
    monkeypatch.setattr(sys, "argv", ["so_sanh_engine.py", "--ra", str(out),
                        "--giay", "2", "--engines", "remotion", "--aspect", "9:16",
                        "--fixture", str(fixture), "--remotion-native"])
    calls = []

    def render(scene, style, seconds, aspect, path, **kwargs):
        calls.append((scene.layout, style, kwargs))
        path.write_bytes(b"video")
        return {"render_engine": "remotion", "render_variant": "native", "width": 1080, "height": 1920}

    monkeypatch.setattr(so_sanh_engine, "render_scene", render)
    assert so_sanh_engine.main() == 0
    assert calls[0][0] == "CHECKLIST"
    assert calls[0][1]["remotion_native"] is True
    assert calls[0][2]["word_times"] == [0, .2, .4, .7, 1, 1.2, 1.4, 1.6]
    report = json.loads((out / "bao_cao_so_sanh.json").read_text(encoding="utf-8"))
    assert report[0]["render_variant"] == "native"
    assert report[0]["status"] == "passed"


def test_so_sanh_khong_nhan_iframe_lam_native(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["so_sanh_engine.py", "--ra", str(tmp_path),
                        "--giay", "1", "--engines", "remotion", "--aspect", "9:16", "--remotion-native"])

    def render(*args, **kwargs):
        args[4].write_bytes(b"video")
        return {"render_engine": "remotion", "render_variant": "legacy_html", "width": 1080, "height": 1920}

    monkeypatch.setattr(so_sanh_engine, "render_scene", render)
    assert so_sanh_engine.main() == 1
