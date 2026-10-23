# -*- coding: utf-8 -*-
"""Công cụ dòng lệnh CLI xóa watermark Veo / Gemini AI cho video (v0.6.5-demo).
Sử dụng:
    python xoa_watermark_veo.py -i <video_goc.mp4> -o <video_sach.mp4>
    python xoa_watermark_veo.py -d <thu_muc_chua_video>
"""

import argparse
import pathlib
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

CURRENT_DIR = pathlib.Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from veo_watermark_remover import veo_remover

def main():
    parser = argparse.ArgumentParser(
        description="Khử sạch logo / watermark Google Veo & Gemini AI khỏi video bằng Reverse Alpha Blending."
    )
    parser.add_argument("-i", "--input", help="Đường dẫn tệp video cần xóa watermark")
    parser.add_argument("-o", "--output", help="Đường dẫn tệp video đầu ra sau khi xử lý (tùy chọn)")
    parser.add_argument("-d", "--dir", help="Đường dẫn thư mục chứa nhiều video cần khử watermark hàng loạt")
    parser.add_argument("--cpu", action="store_true", default=True, help="Sử dụng chế độ CPU an toàn (mặc định)")
    parser.add_argument("--mark", default="auto", choices=["auto", "diamond", "veo"], help="Kiểu watermark")
    parser.add_argument("--denoise", default=None, choices=["ai", "ns", "telea", "soft", "off"], help="Phương thức làm mịn nền")
    parser.add_argument("--region", default=None, help="Vùng watermark cố định x,y,w,h (nếu cần)")
    parser.add_argument("--veo-alpha", type=float, default=None, help="Cường độ alpha thủ công")

    args = parser.parse_args()

    if not args.input and not args.dir:
        parser.print_help()
        print("\nVui lòng cung cấp ít nhất một tệp video (-i) hoặc thư mục (-d).")
        sys.exit(1)

    if not veo_remover.is_available():
        print(f"Lỗi: Không tìm thấy công cụ thực thi tại {veo_remover.exe_path}")
        sys.exit(1)

    if args.input:
        in_path = pathlib.Path(args.input).resolve()
        if not in_path.exists():
            print(f"Lỗi: Không tìm thấy tệp {in_path}")
            sys.exit(1)

        if args.output:
            out_path = pathlib.Path(args.output).resolve()
        else:
            out_path = in_path.parent / f"{in_path.stem}_cleaned{in_path.suffix}"

        print(f"Bắt đầu xử lý: {in_path.name} -> {out_path.name}")
        t0 = time.time()
        res = veo_remover.remove_watermark(
            input_video_path=in_path,
            output_video_path=out_path,
            use_cpu=args.cpu,
            watermark_type=args.mark,
            denoise_method=args.denoise,
            region=args.region,
            veo_alpha=args.veo_alpha
        )
        print(f"Kết quả: {res['status']} | Thời gian: {time.time()-t0:.2f}s | Kích thước: {res.get('byte_size', 0)} bytes")

    if args.dir:
        dir_path = pathlib.Path(args.dir).resolve()
        if not dir_path.is_dir():
            print(f"Lỗi: Không tìm thấy thư mục {dir_path}")
            sys.exit(1)

        video_files = list(dir_path.glob("*.mp4")) + list(dir_path.glob("*.mov"))
        cleaned_dir = dir_path / "cleaned_veo"
        cleaned_dir.mkdir(parents=True, exist_ok=True)

        print(f"Tìm thấy {len(video_files)} video trong thư mục. Đang tiến hành khử watermark hàng loạt...")
        count = 0
        for vid in video_files:
            if "_cleaned" in vid.name:
                continue
            out_vid = cleaned_dir / f"{vid.stem}_cleaned{vid.suffix}"
            try:
                veo_remover.remove_watermark(
                    input_video_path=vid,
                    output_video_path=out_vid,
                    use_cpu=args.cpu,
                    watermark_type=args.mark,
                    denoise_method=args.denoise
                )
                count += 1
            except Exception as e:
                print(f"Lỗi khi xử lý {vid.name}: {e}")

        print(f"Hoàn thành khử watermark hàng loạt: {count}/{len(video_files)} video đã xử lý thành công.")

if __name__ == "__main__":
    main()
