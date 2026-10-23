"""Chạy kiểm thử phân quyền trong tiến trình riêng, chỉ cho phép DB kiểm thử RAM."""

import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone


def main() -> int:
    thu_muc_lam_viec = Path(__file__).resolve().parents[1]
    thu_muc_bang_chung = thu_muc_lam_viec.parent / '08_kiem_thu' / 'bang_chung'
    cac_thu_muc = ('baha_auth', 'sin_content_api', 'sin_content_workers')
    cac_tep = []
    for ten in cac_thu_muc:
        duong_dan = thu_muc_lam_viec / ten
        for tep in duong_dan.rglob('*.py'):
            if '__pycache__' not in tep.parts:
                cac_tep.append(tep)
    cac_tep.append(thu_muc_lam_viec / 'sin_creator_os/src/app/(main)/team/page.tsx')

    def ma_bam():
        return {
            str(tep.relative_to(thu_muc_lam_viec)): hashlib.sha256(tep.read_bytes()).hexdigest()
            for tep in sorted(cac_tep)
        }

    truoc = ma_bam()
    moi_truong = os.environ.copy()
    moi_truong.update({
        'DATABASE_URL': 'sqlite:///:memory:',
        'BAHA_AUTH_DATABASE_URL': 'sqlite:///:memory:',
        'PYTHONIOENCODING': 'utf-8',
        'PYTHONDONTWRITEBYTECODE': '1',
    })
    cac_bo = (
        ('baha_auth', ['tests']),
        ('sin_content_api', ['tests/test_tich_hop_phan_quyen.py']),
        ('sin_content_workers', ['tests/test_kiem_tra_quyen_worker.py']),
    )
    ket_qua = []
    for ten, cac_bai in cac_bo:
        lenh = [sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', *cac_bai]
        chay = subprocess.run(
            lenh, cwd=thu_muc_lam_viec / ten, env=moi_truong,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding='utf-8', errors='replace', timeout=180,
        )
        ten_log = f'kiem_thu_tong_hop_phan_quyen_{ten}_2026_10_21.txt'
        (thu_muc_bang_chung / ten_log).write_text(
            'Cơ sở dữ liệu: chỉ trong RAM; không gọi nhà cung cấp thật.\n'
            + 'Lệnh: python -m pytest -q -p no:cacheprovider ' + ' '.join(cac_bai)
            + f'\nThư mục: {ten}\nMã thoát: {chay.returncode}\n\n'
            + chay.stdout, encoding='utf-8',
        )
        ket_qua.append({'bo': ten, 'ma_thoat': chay.returncode, 'nhat_ky': ten_log})
        print(f'{ten}: mã thoát {chay.returncode}', flush=True)
        print(chay.stdout, flush=True)

    loi_cu_phap = []
    for tep in cac_tep:
        if tep.suffix == '.py':
            try:
                ast.parse(tep.read_text(encoding='utf-8-sig'), filename=str(tep))
            except SyntaxError as loi:
                loi_cu_phap.append({'tep': str(tep.relative_to(thu_muc_lam_viec)), 'loi': str(loi)})
    sau = ma_bam()
    thay_doi = [tep for tep, bam in truoc.items() if sau.get(tep) != bam]
    tong_hop = {
        'thoi_diem_utc': datetime.now(timezone.utc).isoformat(),
        'cac_bo_kiem_thu': ket_qua,
        'loi_cu_phap': loi_cu_phap,
        'tep_thay_doi_trong_luc_kiem_thu': thay_doi,
        'ma_bam_sau_kiem_thu': sau,
        'gioi_han': [
            'Chỉ kiểm thử security tích hợp mới của API nghiệp vụ, chưa xác nhận toàn bộ legacy API suite.',
            'Chưa kiểm chứng PostgreSQL/RLS, trình duyệt, tải/đồng thời trên PostgreSQL, provider, staging hoặc production.',
        ],
    }
    (thu_muc_bang_chung / 'ket_qua_tong_hop_sua_phan_quyen_2026_10_21.json').write_text(
        json.dumps(tong_hop, ensure_ascii=False, indent=2), encoding='utf-8',
    )
    return int(bool(loi_cu_phap or thay_doi or any(bo['ma_thoat'] for bo in ket_qua)))


if __name__ == '__main__':
    raise SystemExit(main())
