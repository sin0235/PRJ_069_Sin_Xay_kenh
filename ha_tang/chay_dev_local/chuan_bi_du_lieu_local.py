"""Sao lưu SQLite nhất quán sang local; giữ nguyên dữ liệu và khóa mã hóa hiện hữu."""
import argparse
import json
from pathlib import Path
import sqlite3
from dotenv import dotenv_values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-env', type=Path, required=True)
    parser.add_argument('--source-data', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    env_path = root / '.env.dev'
    if env_path.exists():
        raise SystemExit('LOCAL_ENV_ALREADY_EXISTS: Không ghi đè cấu hình đã có.')
    values = {key: value for key, value in dotenv_values(args.source_env).items() if value is not None}
    for key in ('BAHA_AUTH_JWT_SECRET', 'BAHA_AUTH_JWT_ISSUER', 'BAHA_AUTH_JWT_AUDIENCE', 'LLM_ENCRYPTION_MASTER_KEY'):
        if not values.get(key):
            raise SystemExit('LOCAL_REQUIRED_SECRET_MISSING: ' + key)
    data = root / 'data'
    data.mkdir(parents=True, exist_ok=True)
    for name in ('sin_content_production.db', 'baha_auth_production.db', 'sin_dieu_phoi_dung.db'):
        source, target = args.source_data / name, data / name
        if not source.is_file() or source.stat().st_size == 0 or target.exists():
            continue
        with sqlite3.connect(f'file:{source}?mode=ro', uri=True) as old, sqlite3.connect(target) as new:
            old.backup(new)
    if not (data / 'sin_content_production.db').is_file() or not (data / 'baha_auth_production.db').is_file():
        raise SystemExit('LOCAL_SOURCE_DATABASE_MISSING')
    values.update({
        'APP_ENV': 'production', 'TESTING': '0', 'DEV_AUTH_BYPASS': '0', 'SYNTHETIC_DATA_ALLOWED': 'false',
        'DATABASE_URL': 'sqlite:///' + (data / 'sin_content_production.db').as_posix(),
        'BAHA_AUTH_DATABASE_URL': 'sqlite:///' + (data / 'baha_auth_production.db').as_posix(),
        'SIN_DUNG_DB_PATH': str(data / 'sin_dieu_phoi_dung.db'),
        'MEDIA_ROOT_DIR': str(data / 'media_assets'), 'FLOW_PROFILE_ROOT': str(data / 'flow_profiles'),
        'WORKER_HEARTBEAT_PATH': str(data / 'runtime' / 'worker.json'),
        'AUTH_COOKIE_SECURE': 'true', 'CONTENT_VIDEO_WORKER_ENABLED': '0',
        'AUTH_ALLOWED_ORIGINS': 'https://nhap-xaykenh-prj069.bahagroup.vn',
        'FLOW_DESKTOP_ALLOWED_ORIGINS': 'https://nhap-xaykenh-prj069.bahagroup.vn',
        'FLOW_CONTROL_URL': 'http://127.0.0.1:8090', 'BROWSER_CHANNEL': 'msedge',
        'REMOTE_COMPUTE_MODE': 'github', 'REMOTE_GITHUB_DISPATCH': 'gh',
        'REMOTE_PUBLIC_ORIGIN': 'https://nhap-xaykenh-prj069.bahagroup.vn',
        'REMOTE_GITHUB_REPOSITORY': 'sin0235/PRJ_069_Sin_Xay_kenh', 'REMOTE_GITHUB_REPOSITORY_ID': '1430829979',
        'REMOTE_GITHUB_REF': 'dev/local-remote-video-tests', 'PRJ069_ENGINE_WORKERS': '1',
        'FLOW_NOVNC_WEB_ROOT': '',
    })
    env_path.write_text('\n'.join(f'{key}={json.dumps(value, ensure_ascii=False)}' for key, value in sorted(values.items())) + '\n', encoding='utf-8')
    print('LOCAL_DATA_COPIED')


if __name__ == '__main__':
    main()
