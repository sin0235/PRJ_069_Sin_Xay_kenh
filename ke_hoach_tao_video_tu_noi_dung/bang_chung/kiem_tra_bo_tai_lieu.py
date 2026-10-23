"""Kiểm tra tính toàn vẹn hồ sơ nghiên cứu; không thay mã nguồn sản phẩm."""

import hashlib
import json
import re
from pathlib import Path

thu_muc = Path(__file__).resolve().parents[1]
goc = thu_muc.parents[1]
tep_khao_sat = thu_muc / "bang_chung/khao_sat_thuc_te.json"
khao_sat = json.loads(tep_khao_sat.read_text(encoding="utf-8"))
khao_sat["runtime"]["http://127.0.0.1:3000/video-studio"]["noi_dung"] = (
    "Trang HTML có phản hồi; chưa xác minh thao tác đăng nhập."
)
tep_khao_sat.write_text(json.dumps(khao_sat, ensure_ascii=False, indent=2), encoding="utf-8")

ten_tep = [
    "nghien_cuu_hien_trang_va_phuong_an.md",
    "dac_ta_bo_tao_video_hoan_chinh.md",
    "ke_hoach_trien_khai_va_checklist.md",
    "ma_tran_nghiem_thu.md",
    "hop_dong_harness_llm_truoc_flow.md",
    "quy_chuan_phong_cach_kenh.md",
    "quy_uoc_thi_cong_song_song.md",
]
ket_qua = {"phien_ban_ke_hoach": "2.0", "tep": []}
for ten in ten_tep:
    tep = thu_muc / ten
    noi_dung = tep.read_text(encoding="utf-8")
    assert "\ufffd" not in noi_dung and "\x00" not in noi_dung, ten
    assert not any(0x1F000 <= ord(ky_tu) <= 0x1FAFF for ky_tu in noi_dung), ten
    assert noi_dung.count("```") % 2 == 0, ten
    ket_qua["tep"].append({"ten": ten, "sha256": hashlib.sha256(tep.read_bytes()).hexdigest()})

ke_hoach = (thu_muc / ten_tep[2]).read_text(encoding="utf-8")
gates = re.findall(r"^### (G\d+) ", ke_hoach, re.MULTILINE)
assert gates == [f"G{i}" for i in range(10)], gates
ket_qua["so_gate"] = len(gates)
ket_qua["so_o_checklist_chua_thi_cong"] = ke_hoach.count("- [ ]")
ma_tran = (thu_muc / ten_tep[3]).read_text(encoding="utf-8")
ma_ca = re.findall(r"^\| (NT\d+) \|", ma_tran, re.MULTILINE)
assert ma_ca == [f"NT{i:02}" for i in range(1, 43)], ma_ca
ket_qua["so_ca_nghiem_thu"] = len(ma_ca)
dac_ta = (thu_muc / ten_tep[1]).read_text(encoding="utf-8")
khoang = re.findall(r"^\| c\d+ \| (\d+)–(\d+) \|", dac_ta, re.MULTILINE)
assert len(khoang) == 12
moc = 0
for dau, cuoi in khoang:
    assert int(dau) == moc and int(cuoi) > moc
    moc = int(cuoi)
assert moc == 120
ket_qua["storyboard_mau"] = {"so_canh": len(khoang), "giay": moc, "frame_30_fps": moc * 30}
drift = []
for item in khao_sat["tep_nguon"]:
    tep = goc / item["duong_dan"]
    if hashlib.sha256(tep.read_bytes()).hexdigest() != item["sha256"]:
        drift.append(item["duong_dan"])
ket_qua["tep_nguon_khac_baseline_khao_sat"] = drift
ket_qua["gioi_han_hash"] = "Đối chiếu baseline khảo sát, không suy ai đã sửa và không ghi đè thay đổi hiện hữu."
assert hashlib.sha256((thu_muc / "dinh_huong_goc_cua_founder.md").read_bytes()).hexdigest() == khao_sat["dac_ta_goc"]["sha256"]
ket_qua["ban_sao_dac_ta_goc_khop_hash"] = True
assert (thu_muc / "bang_chung/ra_soat_doc_lap_ke_hoach.md").is_file()
ket_qua["ra_soat_doc_lap_v1"] = "Xem biên bản phiên 1.0; không thay nghiệm thu runtime."
assert (thu_muc / "bang_chung/ra_soat_doc_lap_ke_hoach_v2.md").is_file()
ket_qua["ra_soat_tai_lieu_v2"] = "Không phát hiện lỗi quan trọng về owner, contract/style mapping, dependency waves và Harness gate; chưa kiểm runtime."
harness = (thu_muc / ten_tep[4]).read_text(encoding="utf-8")
for cum in ["KhoaPhongCach", "DanhGiaLLM", "LenhTaoShot", "BienNhanHarness", "CHO_LLM", "chuan_bi_lenh", "phat_lenh", "15 phút", "call-count"]:
    assert cum in harness, cum
style = (thu_muc / ten_tep[5]).read_text(encoding="utf-8")
for cum in ["KhoaPhongCach", "company_style", "channel_binding", "style_snapshot_hash", "baha_giai_thich_cong_nghe", "2 lượt", "3 video"]:
    assert cum in style, cum
song_song = (thu_muc / ten_tep[6]).read_text(encoding="utf-8")
for cum in ["cong_harness.py", "phong_cach_kenh.py", "kiem_thu_cong_harness.py", "kiem_thu_phong_cach_kenh.py", "TTL 30 phút", "5 phút", "W0", "W5", "3 worker", "SIN_DUNG_DB_PATH"]:
    assert cum in song_song, cum
for ten in ten_tep[4:]:
    assert ten in ke_hoach and ten in dac_ta and ten in ma_tran, ten
ket_qua["kiem_tra_bo_sung_v2"] = "Đủ liên kết phụ lục, hợp đồng Harness/style và ownership/checklist song song; đây là kiểm tài liệu."

log_bytes = (thu_muc / "bang_chung/kiem_thu_co_so.txt").read_bytes()
encoding = "utf-16" if log_bytes.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
log = log_bytes.decode(encoding)
assert "45 passed, 1 warning" in log
ket_qua["kiem_thu_co_so"] = {
    "lenh": "python -m pytest tests/test_video_prompt_compiler.py tests/test_media_studio_video.py tests/test_harness_dao_dien.py -q -p no:cacheprovider",
    "cwd": "03_ban_lam_viec/sin_content_api",
    "ket_qua_phien_khao_sat_v1": "45 đạt, 1 cảnh báo deprecation, mã thoát 0; không chạy lại backend trong phiên chỉ sửa kế hoạch v2",
    "gioi_han": "Có mô phỏng provider; không chứng minh dây chuyền AUTO 120 giây đã hoạt động.",
}
ket_qua["ket_qua"] = "Đạt kiểm tra hồ sơ; chưa nghiệm thu sản phẩm mới."
duong_dan = thu_muc / "bang_chung/ket_qua_ra_soat_tai_lieu_v2.json"
duong_dan.write_text(json.dumps(ket_qua, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(ket_qua, ensure_ascii=False, indent=2))
