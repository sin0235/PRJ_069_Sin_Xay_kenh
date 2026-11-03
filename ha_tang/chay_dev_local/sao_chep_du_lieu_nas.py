"""Đọc snapshot DB và cấu hình hiện hữu qua SSH; không build hoặc sửa dịch vụ NAS."""
import base64
import getpass
import json
from pathlib import Path
import re
import shlex
import sys
import paramiko
from dotenv import dotenv_values, set_key


def main():
    root = Path(__file__).resolve().parent
    password = getpass.getpass('Mat khau SSH: ')
    ssh = paramiko.SSHClient()
    ssh.load_host_keys(str(Path.home() / '.ssh' / 'known_hosts'))
    ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
    ssh.connect('192.168.1.175', username='tts_it_15', password=password, look_for_keys=False, allow_agent=False, timeout=15)
    def sudo(command):
        stdin, stdout, stderr = ssh.exec_command('sudo -S -p "" ' + command, timeout=60)
        stdin.write(password + '\n')
        stdin.flush()
        payload = stdout.read()
        if stdout.channel.recv_exit_status():
            error = stderr.read().decode(errors='replace').strip()
            raise RuntimeError('NAS_READ_FAILED: ' + error[-500:])
        return payload
    try:
        rows = sudo("docker ps --filter label=com.docker.compose.project=prj069-xaykenh-nhap --filter label=com.docker.compose.service=api --format '{{.ID}}'").decode().split()
        if not rows:
            inventory = sudo("docker ps -a --format '{{.ID}}|{{.Names}}|{{.Image}}'").decode().splitlines()
            candidates = [line.split('|') for line in inventory if 'prj069' in line.lower() and re.search(r'[-_]api[-_]', line.lower())]
            if len(candidates) == 1:
                rows = [candidates[0][0]]
            else:
                print('NAS_CONTAINER_CANDIDATES: ' + json.dumps([line for line in inventory if 'prj069' in line.lower()]))
        if len(rows) != 1 or not re.fullmatch(r'[a-f0-9]{12,64}', rows[0]):
            raise RuntimeError('NAS_API_CONTAINER_NOT_FOUND')
        cid = rows[0]
        env = json.loads(sudo('docker inspect ' + cid + " --format '{{json .Config.Env}}'"))
        values = dict(item.split('=', 1) for item in env if '=' in item)
        # Snapshot trong RAM của container, không tạo bản sao DB hoặc tệp tạm trên NAS.
        running = json.loads(sudo('docker inspect ' + cid + " --format '{{json .State.Running}}'"))
        data_root = '/data'
        if not running:
            mounts = json.loads(sudo('docker inspect ' + cid + " --format '{{json .Mounts}}'"))
            data_root = next(item['Source'] for item in mounts if item['Destination'] == '/data')
        code = '''import sqlite3,base64,json
from pathlib import Path
result={}
for name in ['sin_content_production.db','baha_auth_production.db','sin_dieu_phoi_dung.db']:
 p=Path(DATA_ROOT)/name
 if not p.is_file() or p.stat().st_size==0: continue
 with sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True) as source, sqlite3.connect(':memory:') as dest:
  source.backup(dest)
  result[name]=base64.b64encode(('\\n'.join(dest.iterdump())).encode()).decode()
print(json.dumps(result))'''
        code = code.replace('DATA_ROOT', repr(data_root))
        command = ('docker exec ' + cid + ' python -c ') if running else 'python3 -c '
        snapshots = json.loads(sudo(command + shlex.quote(code)))
        data = root / 'data'
        for name, encoded in snapshots.items():
            target = data / name
            if target.exists():
                target.rename(target.with_name(target.name + '.before_nas_snapshot'))
            with __import__('sqlite3').connect(target) as destination:
                destination.executescript(base64.b64decode(encoded, validate=True).decode())
        for key in ('BAHA_AUTH_JWT_SECRET', 'BAHA_AUTH_JWT_ISSUER', 'BAHA_AUTH_JWT_AUDIENCE',
                    'LLM_ENCRYPTION_MASTER_KEY', 'AUTH_OWNER_EMAIL', 'SIN_WORKSPACE_ID', 'SIN_WORKSPACE_NAME'):
            if values.get(key):
                set_key(root / '.env.dev', key, values[key])
        print('NAS_SNAPSHOT_COPIED: ' + str(len(snapshots)))
    finally:
        ssh.close()


if __name__ == '__main__':
    main()
