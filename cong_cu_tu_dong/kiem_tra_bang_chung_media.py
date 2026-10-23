#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Bộ kiểm định bằng chứng ngoại tuyến cho BAHA Media Studio (P1 Production).
Tương thích hoàn toàn Windows và Linux (sử dụng sys.executable thay cho python3).
Chạy: python 03_ban_lam_viec/cong_cu_tu_dong/kiem_tra_bang_chung_media.py <duong_dan_manifest.json> [--require-all-pass]
"""
import hashlib
import json
import os
import pathlib
import sys

# Đảm bảo UTF-8 trên Windows console
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

def error(msg, errs):
    errs.append(msg)

def load(path):
    return json.loads(path.read_text(encoding='utf-8'))

def main():
    if len(sys.argv) < 2:
        print("Cú pháp: python 03_ban_lam_viec/cong_cu_tu_dong/kiem_tra_bang_chung_media.py <duong_dan_manifest.json> [--require-all-pass]")
        return 64

    path = pathlib.Path(sys.argv[1]).resolve()
    strict = "--require-all-pass" in sys.argv[2:]

    if not path.is_file():
        print(f"Lỗi: Không tìm thấy tệp manifest tại: {path}")
        return 2

    data = load(path)
    
    # Tìm index từ thư mục pack nguyên bản
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    index_path = repo_root / "02_nguyen_ban_giai_nen" / "baha_ai_media_studio_pack" / "BAHA_AI_Media_Studio_Implementation_Pack_v1" / "schemas" / "acceptance-index.json"
    
    if not index_path.is_file():
        print(f"Lỗi: Không tìm thấy acceptance-index.json tại: {index_path}")
        return 2

    index = load(index_path)
    phase = data.get("phase")
    errors = []

    # Kiểm tra hỗ trợ thêm gói Google Flow Addendum v1.1
    flow_cases_path = repo_root / "02_nguyen_ban_giai_nen" / "baha_creator_studio_flow_addendum_v1_1" / "BAHA_Group_Creator_Studio_Anti_Plan_v1_1" / "GOOGLE_FLOW_ACCEPTANCE_CASES.json"
    flow_cases = []
    if flow_cases_path.is_file():
        flow_data = load(flow_cases_path)
        flow_cases = flow_data.get("cases", [])

    is_flow_phase = False
    expected = {}
    if phase in index:
        expected = {o["id"]: o["required_evidence"] for o in index[phase]}
    else:
        # Ánh xạ pha kết hợp (ví dụ: P14_GF05 -> GF05, P08_GF04 -> GF04)
        target_gf = None
        for code in ["GF00", "GF01", "GF02", "GF03", "GF04", "GF05", "GF06"]:
            if code in phase:
                target_gf = code
                break
        
        if target_gf:
            matched_cases = [c for c in flow_cases if c.get("phase") == target_gf]
            if matched_cases:
                is_flow_phase = True
                expected = {c["id"]: c.get("mode", "LOCAL_TESTED") for c in matched_cases}

    if not expected:
        error(f"Pha không xác định trong index: {phase}", errors)
        print(errors)
        return 2
    tests = data.get("cases", [])
    keys = [t.get("test_id") for t in tests]

    if len(keys) != len(set(keys)):
        error("Trùng lặp test_id trong manifest", errors)

    if set(keys) != set(expected):
        error("Test cases không khớp: missing=" + str(sorted(set(expected) - set(keys))) +
              " extra=" + str(sorted(set(keys) - set(expected))), errors)

    if data.get("repo_commit") in (None, "", "NOT_SET"):
        error("Thiếu repo_commit thực tế", errors)

    if data.get("environment") in (None, "", "NOT_SET"):
        error("Thiếu environment thực tế", errors)

    if not data.get("generated_at"):
        error("Thiếu generated_at", errors)

    # Các case bắt buộc có tệp nhị phân media thực tế
    live_media_required = set("C02 C03 C04 D03 D04 D05 E01 E02 E03 E04 F01 F02 F04 G01".split())
    counts = {k: 0 for k in ["PASS", "FAIL", "BLOCKED", "NOT_RUN", "IN_PROGRESS", "NOT_SUPPORTED"]}

    for t in tests:
        tid = t.get("test_id", "?")
        level = t.get("evidence_level")
        status = t.get("status")

        if status not in counts:
            error(f"{tid}: Trạng thái không hợp lệ: {status}", errors)
            continue

        counts[status] += 1

        if tid in expected and level != expected[tid]:
            error(f"{tid}: evidence_level không khớp: kỳ vọng {expected[tid]}, nhận {level}", errors)

        if status == "PASS":
            if not str(t.get("observed", "")).strip() or "No execution yet" in t.get("observed", ""):
                error(f"{tid}: Khai báo PASS nhưng thiếu nội dung quan sát thực tế (observed)", errors)
            if not t.get("artifacts"):
                error(f"{tid}: Khai báo PASS nhưng không có tệp đính kèm (artifacts)", errors)
            if level == "LOCAL_TESTED":
                if not t.get("command") or t.get("exit_code") != 0:
                    error(f"{tid}: LOCAL PASS thiếu command hoặc exit code khác 0", errors)
            if level == "DOC_VERIFIED":
                if not t.get("source_urls"):
                    error(f"{tid}: DOC PASS bắt buộc liệt kê source_urls", errors)
            if level == "LIVE_VERIFIED":
                if not t.get("provider_request_id") and not t.get("external_ui_proof"):
                    error(f"{tid}: LIVE PASS bắt buộc có provider_request_id hoặc external_ui_proof", errors)
                if not t.get("independent_qa_reference"):
                    error(f"{tid}: LIVE PASS bắt buộc có independent_qa_reference", errors)
                if tid in live_media_required:
                    if not any(a.get("kind") == "media" for a in t.get("artifacts", [])):
                        error(f"{tid}: LIVE PASS bắt buộc có tệp media thực (kind=media)", errors)
                    if not t.get("media_probe_ref"):
                        error(f"{tid}: LIVE PASS bắt buộc có media_probe_ref", errors)
            if level == "HUMAN_VERIFIED":
                if not t.get("human_reviewer") or not t.get("human_review_reference"):
                    error(f"{tid}: HUMAN PASS bắt buộc có human_reviewer và human_review_reference có chữ ký", errors)

        if status in ("BLOCKED", "NOT_SUPPORTED") and not t.get("blocker_reason"):
            error(f"{tid}: Trạng thái BLOCKED/NOT_SUPPORTED bắt buộc có blocker_reason", errors)

        for a in t.get("artifacts", []):
            rel = a.get("relative_path", "")
            relpath = pathlib.Path(rel)
            if relpath.is_absolute() or ".." in relpath.parts:
                error(f"{tid}: Đường dẫn artifact phải là đường dẫn tương đối an toàn: {rel}", errors)
                continue
            absfile = (path.parent / relpath).resolve()
            if path.parent not in absfile.parents:
                error(f"{tid}: Artifact nằm ngoài thư mục bằng chứng", errors)
                continue
            if not absfile.is_file() or absfile.stat().st_size == 0:
                error(f"{tid}: Artifact thiếu hoặc rỗng (0 bytes): {rel}", errors)
                continue
            h = hashlib.sha256(absfile.read_bytes()).hexdigest()
            if h.lower() != a.get("sha256", "").lower():
                error(f"{tid}: Mã băm SHA256 không khớp với thực tế: {rel} (khai báo {a.get('sha256')}, thực tế {h})", errors)

    if strict and any(v for k, v in counts.items() if k != "PASS"):
        error("NO_GO: Tất cả các bài kiểm thử bắt buộc chưa đạt PASS 100%", errors)

    if errors:
        print("[THẤT BẠI] Phát hiện các lỗi kiểm định bằng chứng:")
        for e in errors:
            print(f"  - {e}")
        return 2

    print(f"[THÀNH CÔNG] Xác thực tính toàn vẹn của manifest: {path.name}")
    print(f"  Thống kê trạng thái: {counts}")
    return 0

if __name__ == '__main__':
    sys.exit(main())
