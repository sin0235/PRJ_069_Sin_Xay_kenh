"""Kiểm tra xuất ZIP khi thư mục media gần giới hạn đường dẫn Windows."""
import hashlib
import json
from types import SimpleNamespace
import zipfile

from src.modules.tao_video_noi_dung.runner import _write_export_package
from src.schemas.contracts import TimelineDocument


def test_xuat_zip_duong_dan_dai(tmp_path, monkeypatch):
    thu_muc = tmp_path / ("a" * max(1, 175 - len(str(tmp_path))))
    thu_muc.mkdir()
    video = thu_muc / "video.mp4"
    video.write_bytes(b"video")
    goi = thu_muc / "content_video_2cabaeda-fffc-48db-80f2-d6b67e578deb_v1_export.zip"
    mo_zip = zipfile.ZipFile

    def mo_zip_gioi_han(duong_dan, *args, **kwargs):
        if len(str(duong_dan)) >= 260:
            raise FileNotFoundError(2, "Đường dẫn vượt giới hạn Windows", str(duong_dan))
        return mo_zip(duong_dan, *args, **kwargs)

    monkeypatch.setattr(zipfile, "ZipFile", mo_zip_gioi_han)
    _write_export_package(
        goi, video, SimpleNamespace(id="run-1"),
        SimpleNamespace(id="plan-1", revision=1, source_content="Nội dung",
                        storyboard_json="{}", style_snapshot_sha256="hash"),
        TimelineDocument(), {"status": "PASS"}, [], [], None,
    )
    with mo_zip(goi) as archive:
        assert archive.read("video/final.mp4") == b"video"
        assert json.loads(archive.read("manifest.json"))["files"]["video/final.mp4"] == hashlib.sha256(b"video").hexdigest()
    assert set(thu_muc.iterdir()) == {video, goi}
