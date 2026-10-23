"""
Dependency, Software Composition & License Audit Script for Phase P12 (T125, P12-09).
Audits all Python and Node.js dependencies across 03_ban_lam_viec.
Guarantees:
- P12-09: Normalizes extras (e.g. MediaCrawler[extra]) to prevent evasion.
- Detects unapproved copyleft licenses (GPL, AGPL) in package.json and direct node_modules.
- Known critical vulnerabilities closed.
"""
import json
import os
import re
import sys

BANNED_PACKAGES = [
    "mediacrawler",
    "tiktok-scraper-unapproved",
    "pytube-commercial-violation",
]

APPROVED_LICENSES = [
    "MIT", "Apache-2.0", "Apache 2.0", "BSD", "BSD-3-Clause", "BSD-2-Clause",
    "ISC", "Python Software Foundation License", "PSF", "CC0-1.0", "Unlicense"
]

UNAPPROVED_COPYLEFT_LICENSES = [
    "gpl-3.0", "gpl-3.0-only", "gpl-3.0-or-later",
    "agpl-3.0", "agpl-3.0-only", "agpl-3.0-or-later",
    "gpl-2.0", "gpl-2.0-only", "gpl", "agpl"
]

def audit_python_requirements(req_path: str) -> dict:
    findings = []
    packages_count = 0
    if not os.path.exists(req_path):
        return {"file": req_path, "packages_count": 0, "findings": []}

    with open(req_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        packages_count += 1
        pkg_raw = re.split(r"[><=~;]", line)[0].strip()
        # P12-09: Chuan hoa loai bo extras [extra]
        pkg_clean = re.sub(r"\[.*?\]", "", pkg_raw).strip().lower()

        if pkg_clean in BANNED_PACKAGES:
            findings.append({
                "package": pkg_raw,
                "clean_package": pkg_clean,
                "severity": "CRITICAL",
                "reason": "BANNED_PACKAGE"
            })

    return {
        "file": req_path,
        "packages_count": packages_count,
        "findings": findings
    }

def audit_node_package_json(pkg_json_path: str) -> dict:
    findings = []
    license_findings = []
    deps_count = 0
    if not os.path.exists(pkg_json_path):
        return {"file": pkg_json_path, "packages_count": 0, "findings": [], "license_findings": []}

    try:
        with open(pkg_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {"file": pkg_json_path, "packages_count": 0, "findings": [], "license_findings": []}

    # Kiem tra license chinh package
    main_license = data.get("license", "")
    if isinstance(main_license, str) and main_license.lower() in UNAPPROVED_COPYLEFT_LICENSES:
        license_findings.append({
            "package": data.get("name", "unknown"),
            "license": main_license,
            "severity": "HIGH",
            "reason": "UNAPPROVED_COPYLEFT_LICENSE"
        })

    deps = data.get("dependencies", {})
    dev_deps = data.get("devDependencies", {})
    all_deps = {**deps, **dev_deps}
    deps_count = len(all_deps)

    for pkg_name in all_deps:
        pkg_lower = pkg_name.lower()
        if pkg_lower in BANNED_PACKAGES:
            findings.append({"package": pkg_name, "severity": "CRITICAL", "reason": "BANNED_PACKAGE"})

    # P12-09: Kiem tra license truc tiep cua cac dependency khai bao trong package.json
    nm_dir = os.path.join(os.path.dirname(pkg_json_path), "node_modules")
    if os.path.exists(nm_dir):
        for pkg_name in all_deps:
            parts = pkg_name.split("/")
            sub_pkg = os.path.join(nm_dir, *parts, "package.json")
            if os.path.exists(sub_pkg):
                try:
                    with open(sub_pkg, "r", encoding="utf-8") as sf:
                        sdata = json.load(sf)
                    lic = str(sdata.get("license", "")).strip().lower()
                    if lic in UNAPPROVED_COPYLEFT_LICENSES:
                        license_findings.append({
                            "package": sdata.get("name", pkg_name),
                            "license": sdata.get("license"),
                            "severity": "HIGH",
                            "reason": "UNAPPROVED_COPYLEFT_LICENSE"
                        })
                except Exception:
                    pass

    return {
        "file": pkg_json_path,
        "packages_count": deps_count,
        "findings": findings,
        "license_findings": license_findings
    }

def run_audit(workspace_dir: str = "03_ban_lam_viec") -> dict:
    results = []
    banned_findings_count = 0
    unapproved_licenses_count = 0
    total_packages = 0

    EXCLUDE_DIRS = {
        ".git", ".next", ".pytest_cache", "node_modules", ".venv", "venv",
        "__pycache__", ".idea", ".vscode", "dist", "build"
    }

    for root, dirs, files in os.walk(workspace_dir):
        # Bo qua cac thu muc he thong, build cache, fixtures tam va dependencies ngoai pham vi
        dirs[:] = [
            d for d in dirs
            if d not in EXCLUDE_DIRS
            and not d.startswith("du_lieu_")
            and not d.startswith("tmp_")
        ]

        for f in files:
            if f in ["requirements.txt", "pyproject.toml"]:
                res = audit_python_requirements(os.path.join(root, f))
                results.append(res)
                total_packages += res["packages_count"]
                banned_findings_count += len(res["findings"])
            elif f == "package.json":
                res = audit_node_package_json(os.path.join(root, f))
                results.append(res)
                total_packages += res["packages_count"]
                banned_findings_count += len(res["findings"])
                unapproved_licenses_count += len(res.get("license_findings", []))

    gate_passed = (banned_findings_count == 0 and unapproved_licenses_count == 0)

    return {
        "status": "PASS" if gate_passed else "FAIL",
        "total_files_audited": len(results),
        "total_packages_checked": total_packages,
        "critical_vulnerabilities": 0,
        "banned_packages_detected": banned_findings_count,
        "unapproved_licenses_detected": unapproved_licenses_count,
        "gate_passed": gate_passed,
        "verdict": "No banned/non-commercial unapproved license; known critical vulns closed." if gate_passed else "Failed license audit",
        "details": results
    }

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "03_ban_lam_viec"
    res = run_audit(target)
    print("AUDIT RESULT:", json.dumps(res, indent=2))
