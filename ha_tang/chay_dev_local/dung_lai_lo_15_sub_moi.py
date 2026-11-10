"""Dựng lại 15 video lô 15 bằng sub mới (ghép lại từ shot đã có, KHÔNG gọi Flow/TTS), rồi xuất ra thư mục riêng.

Chạy: python dung_lai_lo_15_sub_moi.py 17 11 ...   (không đối số = cả 15 bài)
Kết quả: data/runtime/xuat_lo_15_sub_moi/<số>_<tên>.mp4 (remux faststart); không đụng file cũ.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid
from datetime import timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "sin_content_api"), str(ROOT)]

from dotenv import load_dotenv  # noqa: E402

load_dotenv(HERE / ".env.dev", override=True)
os.environ["REMOTE_COMPUTE_MODE"] = "local"   # dựng tại máy, không chuyển việc sang GitHub Actions

from src.database import SessionLocal  # noqa: E402
from src.models.entities import ContentVideoRun  # noqa: E402
from src.modules.tao_video_noi_dung import runner  # noqa: E402
from src.modules.tao_video_noi_dung.service import rerender_run  # noqa: E402

# bài -> (tiền tố run, tên file chính thức đang có trên NAS)
BAI = {
    "01": ("f5f779ad", "01_san_pham_tot_nhung_van_thieu_khach_moi.mp4"),
    "02": ("ae350660", "02_bao_gia_xong_khach_im_lang_mat_don_vi_quy_trinh_ban_hang.mp4"),
    "03": ("d22d5bde", "03_goi_cang_nhieu_khach_cang_cup_may.mp4"),
    "04": ("0e40d514", "04_quang_cao_co_luot_xem_nhung_khong_ra_don.mp4"),
    "06": ("2afef5b7", "06_khach_moi_bo_quen_doanh_thu_tu_khach_cu.mp4"),
    "07": ("7e285aa6", "07_doanh_thu_tang_loi_nhuan_giam.mp4"),
    "08": ("c204b835", "08_ban_duoc_hang_nhung_thieu_tien_tra_luong.mp4"),
    "09": ("1809c15b", "09_khong_vay_duoc_von_van_de_khong_chi_o_ngan_hang.mp4"),
    "10": ("12f6c29f", "10_giam_gia_ban_nhieu_co_the_lo_nang.mp4"),
    "11": ("ee8a18bf", "11_kho_day_hang_nhung_thieu_mon_khach_can.mp4"),
    "12": ("281c7831", "12_doi_xe_chay_lien_tuc_loi_nhuan_thap_quang_duong_rong.mp4"),
    "13": ("37967994", "13_giao_hang_tre_khach_roi_di_quy_trinh_mac_o_dau.mp4"),
    "14": ("39a1a0ac", "14_giam_doc_nghi_mot_ngay_cong_ty_roi_loan.mp4"),
    "17": ("d06ed3e0", "17_bao_cao_nhieu_sep_khong_biet_cong_ty_khoe_hay_yeu.mp4"),
    "18": ("099ddafb", "18_nhan_vien_quay_lai_excel_sau_khi_mua_phan_mem.mp4"),
}
OUT = HERE / "data" / "runtime" / "xuat_lo_15_sub_moi"
FFMPEG = "ffmpeg"


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def main() -> None:
    chon = sys.argv[1:] or list(BAI)
    OUT.mkdir(parents=True, exist_ok=True)
    for so in chon:
        prefix, ten = BAI[so]
        t0 = time.time()
        with SessionLocal() as db:
            run = db.query(ContentVideoRun).filter(ContentVideoRun.id.like(prefix + "%")).one()
            run_id, project_id, ws = run.id, run.project_id, run.workspace_id
            token = str(uuid.uuid4())
            if not runner._acquire_lease(db, token):
                log(f"bài {so}: worker khác đang giữ lease; dừng để không giẫm lên")
                return
            rerender_run(db, project_id, run_id, ws, include_subtitles=True)
            n = db.query(ContentVideoRun).filter(ContentVideoRun.id == run_id, ContentVideoRun.status == "QUEUED").update({
                "status": "RUNNING", "lease_token": token,
                "lease_expires_at": runner._now() + timedelta(seconds=runner.LEASE_SECONDS), "started_at": runner._now(),
            })
            db.commit()
            if n != 1:
                log(f"bài {so}: không nhận được run (worker khác đã lấy?), bỏ qua")
                continue
        log(f"bài {so}: bắt đầu ghép lại run {run_id[:8]}")
        try:
            runner.process_run(run_id, token)
        finally:
            with SessionLocal() as db:
                runner._release_lease(db, token)
        with SessionLocal() as db:
            run = db.get(ContentVideoRun, run_id)
            status, err = run.status, run.error_message
        if status != "COMPLETED":
            log(f"bài {so}: KẾT QUẢ {status} {err}")
            continue
        files = sorted(Path(runner.get_workspace_storage_dir(ws)).glob(f"content_video_{run_id}_v*.mp4"), key=lambda p: p.stat().st_mtime)
        src = files[-1]
        dst = OUT / ten
        subprocess.run([FFMPEG, "-v", "error", "-y", "-i", str(src), "-c", "copy", "-movflags", "+faststart", str(dst)], check=True)
        log(f"bài {so}: xong {status} sau {round(time.time() - t0)} giây ->", dst.name, src.name)


if __name__ == "__main__":
    main()
