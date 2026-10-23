# Test T012: Quet secrets, tokens va credentials trong ma nguon va log
import os
import re
import sys

# Dam bao encoding an toan tren Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SECRET_PATTERNS = [
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
    (r"ghp_[0-9a-zA-Z]{36}", "GitHub Personal Access Token"),
    (r"sk-[a-zA-Z0-9]{32,}", "OpenAI Secret Key"),
    (r"secret_key\s*=\s*['\"][a-zA-Z0-9_\-\.]{20,}['\"]", "Hardcoded Secret Key"),
    (r"tiktok_app_secret\s*=\s*['\"][a-zA-Z0-9]{16,}['\"]", "TikTok App Secret"),
    (r"password\s*=\s*['\"][^'\"]{8,}['\"]", "Hardcoded Password")
]

EXCLUDE_DIRS = [".git", "node_modules", ".venv", "__pycache__", ".gemini", "scratch", ".next", "dist", "build", ".pytest_cache"]
EXCLUDE_FILES = [".env.example", "scan_secrets.py"]

def scan_directory(root_dir: str):
    print("=== T012: SECRETS & CREDENTIALS AUDIT ===")
    print(f"Scanning target directory: {root_dir}")
    violations = []
    scanned_count = 0
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Exclude directories
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        
        for filename in filenames:
            if filename in EXCLUDE_FILES:
                continue
                
            filepath = os.path.join(dirpath, filename)
            # Chi quet cac file text/code
            ext = os.path.splitext(filename)[1].lower()
            if ext in [".py", ".ts", ".tsx", ".js", ".json", ".yaml", ".yml", ".md", ".env", ".cmd", ".ps1"]:
                scanned_count += 1
                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                        for line_idx, line in enumerate(lines, 1):
                            # Bo qua cac placeholder an toan
                            if "sin-offline-secret-key" in line or "sin-dev-secret" in line or "change-me-in-production" in line:
                                continue
                            for pattern, desc in SECRET_PATTERNS:
                                if re.search(pattern, line):
                                    violations.append({
                                        "file": filepath,
                                        "line": line_idx,
                                        "type": desc,
                                        "snippet": line.strip()[:60]
                                    })
                except Exception:
                    pass
                    
    print(f"Scanned files count: {scanned_count}")
    if violations:
        print(f"\n[FAIL] Found {len(violations)} secret exposure violations:")
        for v in violations:
            print(f" - {v['file']}:{v['line']} [{v['type']}]: {v['snippet']}")
        sys.exit(1)
    else:
        print("\n[PASS] Zero committed credentials, tokens or passwords found!")
        print("T012 Result: PASS")
        sys.exit(0)

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    scan_directory(target)
