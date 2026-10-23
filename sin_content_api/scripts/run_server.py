# Script khoi chay FastAPI Server cho SIN Content Intelligence
import uvicorn
import sys
import os
from pathlib import Path

# Them thu muc goc vao sys.path
api_root = Path(__file__).resolve().parents[1]
project_root = api_root.parent.parent
if str(api_root) not in sys.path:
    sys.path.insert(0, str(api_root))
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Thiet lap cac bien moi truong phan quyen va database offline
os.environ.setdefault("APP_ENV", "offline")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{api_root / 'sin_content_offline.db'}")
os.environ.setdefault("BAHA_AUTH_DATABASE_URL", f"sqlite:///{project_root / 'baha_auth_test.db'}")
os.environ.setdefault("BAHA_AUTH_JWT_SECRET", "sin-dev-secret-do-not-use-in-production")
os.environ.setdefault("BAHA_AUTH_JWT_ISSUER", "baha-auth-issuer")
os.environ.setdefault("BAHA_AUTH_JWT_AUDIENCE", "sin-content-test")
os.environ.setdefault("MEDIA_ROOT_DIR", str(project_root / "03_ban_lam_viec" / "media_assets"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"Khoi dong SIN Content Intelligence API tren http://{host}:{port}")
    uvicorn.run("src.main:app", host=host, port=port, reload=False, log_level="info")
