"""Tạo .env và secrets/9rt.env cho dự án triển khai NAS v2.

Chạy một lần trên máy làm việc, không in bí mật ra màn hình. Từ chối ghi đè .env đã có:
đổi khóa mã hóa LLM hoặc khóa phiên sẽ làm hỏng dữ liệu đã khởi tạo.
"""

import argparse
import base64
import getpass
import hashlib
import hmac
import os
import secrets
import sys
import uuid
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

THU_MUC = Path(__file__).resolve().parent
LAN_BAM = 600_000
# Phải trùng workspace_id_for_project("PRJ_069") trong scripts/khoi_tao_production_noi_bo.py.
WORKSPACE_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "baha-group:PRJ_069:sin-xay-kenh:local-production"))
EMAIL_FOUNDER = "phuctoan235@gmail.com"
TEN_HOP_LE = {"llm_api_key", "api_key", "api-key", "llm_base_url", "base_url", "llm_model"}


def tao_hash(mat_khau: str) -> str:
    if len(mat_khau) < 12:
        raise ValueError("Mật khẩu phải có ít nhất 12 ký tự.")
    ma = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")
    muoi = os.urandom(16)
    bam = hashlib.pbkdf2_hmac("sha256", mat_khau.encode("utf-8"), muoi, LAN_BAM)
    return f"pbkdf2_sha256${LAN_BAM}${ma(muoi)}${ma(bam)}"


def kiem_tra_hash(mat_khau: str, ma_hoa: str) -> bool:
    _, lan, muoi, bam = ma_hoa.split("$")
    giai = lambda s: base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
    thu = hashlib.pbkdf2_hmac("sha256", mat_khau.encode("utf-8"), giai(muoi), int(lan))
    return hmac.compare_digest(thu, giai(bam))


def doc_9rt(duong_dan: Path) -> dict[str, str]:
    gia_tri: dict[str, str] = {}
    for dong in duong_dan.read_text(encoding="utf-8-sig").splitlines():
        ten, dau, noi_dung = dong.partition("=")
        if dau and ten.strip().casefold() in TEN_HOP_LE:
            gia_tri[ten.strip().casefold()] = noi_dung.strip()
    khoa = gia_tri.get("llm_api_key") or gia_tri.get("api_key") or gia_tri.get("api-key")
    dia_chi = gia_tri.get("llm_base_url") or gia_tri.get("base_url")
    if not khoa or not dia_chi or not gia_tri.get("llm_model"):
        raise SystemExit("Tệp 9rt.env thiếu LLM_API_KEY, LLM_BASE_URL hoặc LLM_MODEL.")
    return {"khoa": khoa, "dia_chi": dia_chi.rstrip("/"), "model": gia_tri["llm_model"]}


def ghi_rieng_tu(duong_dan: Path, noi_dung: str) -> None:
    duong_dan.parent.mkdir(parents=True, exist_ok=True)
    duong_dan.write_text(noi_dung, encoding="utf-8", newline="\n")
    if os.name != "nt":
        duong_dan.chmod(0o600)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nas-host", default="192.168.1.175", help="Địa chỉ LAN của NAS.")
    parser.add_argument("--nguon-9rt", type=Path, default=THU_MUC.parent / "nas_kiem_thu_that" / "9rt.env",
                        help="Tệp chứa LLM_API_KEY, LLM_BASE_URL, LLM_MODEL.")
    tham_so = parser.parse_args()

    tep_env = THU_MUC / ".env"
    if tep_env.exists():
        raise SystemExit(f"Đã có {tep_env.name}. Không ghi đè; xóa thủ công nếu chắc chắn khởi tạo lại từ đầu.")
    if not tham_so.nguon_9rt.is_file():
        raise SystemExit(f"Không thấy tệp LLM: {tham_so.nguon_9rt}")

    mat_khau = os.environ.get("PRJ069_MAT_KHAU") or getpass.getpass("Mật khẩu đăng nhập Founder (>= 12 ký tự): ")
    if not os.environ.get("PRJ069_MAT_KHAU") and getpass.getpass("Nhập lại mật khẩu: ") != mat_khau:
        raise SystemExit("Hai lần nhập mật khẩu không khớp.")
    ma_hoa = tao_hash(mat_khau)
    assert kiem_tra_hash(mat_khau, ma_hoa)

    llm = doc_9rt(tham_so.nguon_9rt)
    ghi_rieng_tu(THU_MUC / "secrets" / "9rt.env", f"LLM_API_KEY={llm['khoa']}\n")
    ghi_rieng_tu(tep_env, "\n".join([
        "# Sinh bởi tao_cau_hinh.py. Không commit, không gửi qua chat.",
        f"NAS_HOST={tham_so.nas_host}",
        "WEB_PORT=3069",
        "API_PORT=8069",
        f"FOUNDER_EMAIL={EMAIL_FOUNDER}",
        # Dấu nháy đơn để Compose không nội suy ký tự $ trong hash.
        f"FOUNDER_PASSWORD_HASH='{ma_hoa}'",
        f"SIN_WORKSPACE_ID={WORKSPACE_ID}",
        f"BAHA_AUTH_JWT_SECRET={secrets.token_urlsafe(48)}",
        "BAHA_AUTH_JWT_ISSUER=prj069-nas",
        "BAHA_AUTH_JWT_AUDIENCE=sin-content",
        f"LLM_ENCRYPTION_MASTER_KEY={secrets.token_urlsafe(48)}",
        f"LLM_BASE_URL={llm['dia_chi']}",
        f"LLM_MODEL={llm['model']}",
        "FLOW_PROFILE_ID=mac_dinh",
        "# Chỉ dùng khi mở noVNC ra LAN để đăng nhập Flow (xem huong_dan_trien_khai.md):",
        "# FLOW_VNC_BIND=192.168.1.175",
        "# FLOW_VNC_PASSWORD=",
        "",
    ]))
    print(f"Đã tạo {tep_env.name} và secrets/9rt.env (model {llm['model']}).")
    print(f"Địa chỉ giao diện sau khi chạy: http://{tham_so.nas_host}:3069")


if __name__ == "__main__":
    sys.exit(main())
