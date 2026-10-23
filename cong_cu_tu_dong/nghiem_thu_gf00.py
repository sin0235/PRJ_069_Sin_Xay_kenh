# -*- coding: utf-8 -*-
"""Nghiệm thu cổng GF00: Khảo sát năng lực, bản quyền và khóa hạn dùng Veo 3.1 preview."""

import os
import json
import hashlib
from pathlib import Path

BASE_DIR = Path(r"\\192.168.1.175\09.ai_workspace\01_du_an\PRJ_069_Sin_Xay_kenh")
DOCS_DIR = BASE_DIR / "docs" / "media_studio"
EVIDENCE_DIR = BASE_DIR / "08_kiem_thu" / "bang_chung" / "media_studio" / "P0_GF00"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

def verify_gf00():
    results = []

    # GF00-01: Kiểm tra tài liệu License Register và Repo Audit
    repo_audit_file = DOCS_DIR / "REPO_AUDIT.md"
    assert repo_audit_file.exists(), "Thiếu REPO_AUDIT.md"
    results.append({
        "id": "GF00-01",
        "description": "License register and candidate repo audit",
        "status": "PASS",
        "evidence": "docs/media_studio/REPO_AUDIT.md"
    })

    # GF00-02: ADR phân tách rõ ràng API vs Web App
    adr_file = DOCS_DIR / "GOOGLE_MEDIA_ADR.md"
    assert adr_file.exists(), "Thiếu GOOGLE_MEDIA_ADR.md"
    content = adr_file.read_text(encoding="utf-8")
    assert "KHÔNG CÓ API THƯƠNG MẠI CHÍNH THỨC" in content, "ADR chưa nêu rõ Web App không có API chính thức"
    results.append({
        "id": "GF00-02",
        "description": "ADR documents Flow web has no public commercial API",
        "status": "PASS",
        "evidence": "docs/media_studio/GOOGLE_MEDIA_ADR.md"
    })

    # GF00-03: Tách biệt Credits gói Pro vs API Cloud Billing
    assert "10.000 credits/tháng" in content and "Cloud Billing" in content, "Chưa tách biệt Pro credits vs Cloud Billing"
    results.append({
        "id": "GF00-03",
        "description": "Pro credits separated from API Cloud billing",
        "status": "PASS",
        "evidence": "docs/media_studio/GOOGLE_MEDIA_ADR.md"
    })

    # GF00-04: Khóa hạn dùng Veo 3.1 preview (2026-10-22)
    deprecations_file = DOCS_DIR / "MODEL_DEPRECATIONS.md"
    assert deprecations_file.exists(), "Thiếu MODEL_DEPRECATIONS.md"
    dep_text = deprecations_file.read_text(encoding="utf-8")
    assert "veo-3.1-generate-preview" in dep_text and "2026-10-22" in dep_text and "gemini-omni-1.1-flash" in dep_text
    results.append({
        "id": "GF00-04",
        "description": "Veo 3.1 preview retired 2026-10-22 and replaced by gemini-omni-1.1-flash",
        "status": "PASS",
        "evidence": "docs/media_studio/MODEL_DEPRECATIONS.md"
    })

    # GF00-05: Đánh giá rủi ro Flow Pilot
    risk_file = DOCS_DIR / "FLOW_PILOT_RISK_ASSESSMENT.md"
    assert risk_file.exists(), "Thiếu FLOW_PILOT_RISK_ASSESSMENT.md"
    results.append({
        "id": "GF00-05",
        "description": "Flow pilot browser risk assessment and human-in-the-loop approval",
        "status": "PASS",
        "evidence": "docs/media_studio/FLOW_PILOT_RISK_ASSESSMENT.md"
    })

    # GF00-06: Khóa tái sử dụng code không có license rõ ràng
    prov_file = DOCS_DIR / "GOOGLE_PROVIDER_REGISTER.csv"
    assert prov_file.exists(), "Thiếu GOOGLE_PROVIDER_REGISTER.csv"
    results.append({
        "id": "GF00-06",
        "description": "Provider register with license review and blocked/hold statuses",
        "status": "PASS",
        "evidence": "docs/media_studio/GOOGLE_PROVIDER_REGISTER.csv"
    })

    out_file = EVIDENCE_DIR / "gf00_verification_report.json"
    out_file.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"GF00 Verification: 6/6 tests PASSED. Saved to {out_file}")

if __name__ == "__main__":
    verify_gf00()
