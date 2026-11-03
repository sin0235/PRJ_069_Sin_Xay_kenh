"""Kiểm tra cấu hình local cho chay_he_thong.ps1: in một dòng JSON, không in khóa hay token."""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(Path(__file__).with_name('.env.dev'), override=True)
sys.path[:0] = [str(ROOT / 'sin_content_api'), str(ROOT)]

out = {}
workspace = profile = None
try:
    from src.database import SessionLocal
    from src.modules.llm.client import LLMClient
    from src.modules.flow_sessions.models import FlowProfile

    with SessionLocal() as db:
        client = LLMClient.from_db(db)
        if '--sua-llm' in sys.argv and urlsplit(client.base_url).netloc not in ('127.0.0.1:20128', 'localhost:20128'):
            from datetime import datetime, timezone
            from src.models.entities import AuditEvent
            from src.modules.platform_config.service import platform_config_service
            config = platform_config_service.get_or_create_config(db)
            previous, config.base_url = config.base_url, 'http://127.0.0.1:20128/v1'
            config.updated_by, config.updated_at = 'chay_he_thong', datetime.now(timezone.utc).replace(tzinfo=None)
            db.add(AuditEvent(workspace_id='platform', actor_id='chay_he_thong', event_type='PLATFORM_LLM_CONFIG_UPDATE',
                              details=json.dumps({'base_url': config.base_url, 'previous_base_url': previous, 'key_rotated': False})))
            db.commit()
            client = LLMClient.from_db(db)
            out['da_sua_llm'] = True
        out['llm'] = {'host': urlsplit(client.base_url).netloc, 'enabled': bool(client.is_enabled)}
        profiles = db.query(FlowProfile).filter(FlowProfile.workspace_id == os.environ['SIN_WORKSPACE_ID']).all()
        out['flow_profiles'] = len(profiles)
        if len(profiles) == 1:
            workspace, profile = profiles[0].workspace_id, profiles[0].id
except Exception as exc:   # báo tên lỗi, không in nội dung có thể chứa bí mật
    out['loi'] = type(exc).__name__

if workspace and profile:
    cookies = (ROOT / 'ha_tang/chay_dev_local/data/flow_profiles/workspaces' / workspace / 'profiles' / profile
               / 'Default/Network/Cookies')
    wanted = {'SID', 'SAPISID', '__Secure-1PSID', '__Secure-3PSID'}
    try:
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / 'cookies.db'
            shutil.copy2(cookies, copy)
            with sqlite3.connect(copy) as db:
                names = {row[0] for row in db.execute('select name from cookies')}
            out['flow_google_cookie'] = bool(names & wanted)
    except OSError:
        out['flow_google_cookie'] = None   # tệp đang bị trình duyệt giữ khóa
    except sqlite3.Error:
        out['flow_google_cookie'] = None
print(json.dumps(out, ensure_ascii=False))
