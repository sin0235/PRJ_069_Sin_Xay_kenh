"""Tái hiện P12 với DB RAM và tệp giả lập mới; không thao tác DB dự án."""
import copy
import hashlib
import json
import os
from pathlib import Path
import runpy
import sqlite3
import sys
import uuid

API = Path(__file__).resolve().parent
ROOT = API.parents[1]
sys.path.insert(0, str(API))
os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import src.database as database

database.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
database.SessionLocal = sessionmaker(bind=database.engine, autocommit=False, autoflush=False)
context = runpy.run_path(str(API / 'tests/test_staging_evaluation.py'))
from src.models.entities import WorkspaceBudget, CostLedger
from src.modules.staging_reliability.budget_guard import budget_guard
from src.modules.staging_reliability.downstream_executor import _PROCESSED_ARTIFACT_CACHE
import src.modules.staging_reliability.prompt_regression as regression

fixture = context['p12_fixture'].__wrapped__
client = context['client']
results = {'phạm_vi': 'HTTP giữ nguyên RBAC, DB RAM; sao lưu/phục hồi chỉ trên tệp giả lập mới trong vùng làm việc.'}


def request(fixture_data, route, payload, tenant='a'):
    return client.post(route, headers=fixture_data['headers_' + tenant], json=payload)


def execute(fixture_data, key, units, tenant='a'):
    return request(fixture_data, '/v1/staging/tasks/execute', {
        'workspace_id': fixture_data['ws_' + tenant + '_id'], 'task_id': 'tac_vu_' + key,
        'idempotency_key': key, 'estimated_units': units,
    }, tenant)


def allocate(fixture_data, units):
    with database.SessionLocal() as db:
        budget = budget_guard.get_or_create_budget(db, fixture_data['ws_a_id'], units)
        budget.allocated_units = budget.hard_limit_units = units
        db.commit()


def spent(fixture_data):
    with database.SessionLocal() as db:
        return db.query(WorkspaceBudget).filter_by(workspace_id=fixture_data['ws_a_id']).one().spent_units


f = fixture()
key = uuid.uuid4().hex
a, b = execute(f, key, 2), execute(f, key, 2, 'b')
assert a.status_code == b.status_code == 200
assert a.json()['output_artifact_id'] == b.json()['output_artifact_id']
results['cache_khác_tenant'] = {'A': a.json(), 'B': b.json()}

f = fixture()
allocate(f, 5)
key = uuid.uuid4().hex
a = execute(f, key, 2)
_PROCESSED_ARTIFACT_CACHE.clear()
b = execute(f, key, 2)
assert a.status_code == b.status_code == 200 and spent(f) == 4
assert a.json()['output_artifact_id'] != b.json()['output_artifact_id']
results['mất_cache_RAM'] = {'A': a.json(), 'B': b.json(), 'đã_trừ': spent(f)}

f = fixture()
allocate(f, 1)
key = uuid.uuid4().hex
a, b = execute(f, key, 5), execute(f, key, 5)
assert a.status_code == 402 and b.status_code == 200 and spent(f) == 5
results['retry_ledger_REFUSED'] = {'http_đầu': a.status_code, 'http_sau': b.status_code, 'hạn_mức': 1, 'đã_trừ': spent(f)}

f = fixture()
allocate(f, 1)
key = uuid.uuid4().hex
r = request(f, '/v1/staging/budget/reserve', {'workspace_id': f['ws_a_id'], 'task_id': 'nho', 'idempotency_key': key, 'estimated_units': 0.1})
assert r.status_code == 200
r = execute(f, key, 10)
assert r.status_code == 200 and spent(f) == 10
results['đổi_payload_cùng_key'] = {'giữ_chỗ': 0.1, 'ước_tính_sau': 10, 'hạn_mức': 1, 'đã_trừ': spent(f)}

f = fixture()
allocate(f, 1)
s1, s2 = database.SessionLocal(), database.SessionLocal()
ba = s1.query(WorkspaceBudget).filter_by(workspace_id=f['ws_a_id']).one()
bb = s2.query(WorkspaceBudget).filter_by(workspace_id=f['ws_a_id']).one()
x = budget_guard.reserve_budget(s1, f['ws_a_id'], 'a', uuid.uuid4().hex, 'RESEARCH_RUN', 0.8)
y = budget_guard.reserve_budget(s2, f['ws_a_id'], 'b', uuid.uuid4().hex, 'RESEARCH_RUN', 0.8)
with database.SessionLocal() as db:
    budget = db.query(WorkspaceBudget).filter_by(workspace_id=f['ws_a_id']).one()
    total = sum(v.estimated_units for v in db.query(CostLedger).filter_by(workspace_id=f['ws_a_id'], status='RESERVED').all())
    assert total == 1.6 and budget.reserved_units == 0.8
    results['hai_session_giữ_chỗ'] = {'hạn_mức': 1, 'tổng_ledger': total, 'budget_reserved': budget.reserved_units, 'trạng_thái': [x.status, y.status]}
s1.close()
s2.close()

temporary = API / ('du_lieu_tai_hien_p12_' + uuid.uuid4().hex[:8])
assert temporary.is_relative_to(API) and not temporary.exists()
temporary.mkdir()
source = temporary / 'nguon_gia_lap.db'
db = sqlite3.connect(source)
db.execute('CREATE TABLE users (id TEXT, hashed_password TEXT)')
db.execute('INSERT INTO users VALUES (?,?)', ('u1', 'mat_khau_gia_lap_khong_phai_secret'))
db.execute('CREATE TABLE source_observations (id TEXT, raw_payload_json TEXT)')
db.execute('INSERT INTO source_observations VALUES (?,?)', ('o1', json.dumps({'access_token': 'token_gia_lap_p12_khong_co_gia_tri'})))
db.commit()
db.close()
manifest = context['backup_database'](str(source), str(temporary / 'sao_luu'))
backup = temporary / 'sao_luu' / manifest['backup_file']
db = sqlite3.connect(backup)
payload = db.execute('SELECT raw_payload_json FROM source_observations').fetchone()[0]
db.close()
assert 'token_gia_lap_p12_khong_co_gia_tri' in payload
results['backup_chưa_tẩy_token'] = {'manifest_scrubbed': manifest['secrets_scrubbed'], 'manifest_status': manifest['status'], 'token_giả_lập_vẫn_còn': True}

target = temporary / 'dich_gia_lap.db'
assert target.resolve().is_relative_to(temporary.resolve())
db = sqlite3.connect(target)
db.execute('CREATE TABLE du_lieu_can_giu (id INTEGER)')
db.execute('INSERT INTO du_lieu_can_giu VALUES (1)')
db.commit()
db.close()
bad = temporary / 'backup_hong_gia_lap.db'
bad.write_bytes(b'du_lieu_khong_phai_sqlite')
try:
    context['restore_database'](str(bad), str(target), str(temporary / 'manifest_khong_ton_tai.json'))
except Exception as error:
    results['restore_phá_đích'] = {'lỗi': type(error).__name__, 'manifest_không_tồn_tại_vẫn_chạy': True}
assert target.read_bytes() == bad.read_bytes()
results['restore_phá_đích']['đích_bị_thay_bằng_file_hỏng'] = True

original = copy.deepcopy(regression.HELD_OUT_EVALUATION_DATASET)
before = regression.prompt_regression_engine.evaluate_held_out_regression()
try:
    regression.HELD_OUT_EVALUATION_DATASET[0]['candidates'][0]['hook'] = original[0]['excluded_topics'][0] + '; đã quan sát 999999999 lượt xem không có nguồn'
    after = regression.prompt_regression_engine.evaluate_held_out_regression()
    assert before == after and after['evaluation_gate_passed']
finally:
    regression.HELD_OUT_EVALUATION_DATASET[:] = original
results['đánh_giá_chỉ_đếm_nhãn'] = {'thay_hook_cấm_và_số_liệu_không_nguồn_vẫn_đạt': True, 'kết_quả': after, 'số_ứng_viên_mỗi_brief': [len(b['candidates']) for b in original]}

audit_directory = temporary / 'goi_gia_lap'
audit_directory.mkdir()
(audit_directory / 'package.json').write_text(json.dumps({'dependencies': {'goi_gpl_gia_lap': '1.0.0'}}), encoding='utf-8')
dependency = audit_directory / 'node_modules' / 'goi_gpl_gia_lap'
dependency.mkdir(parents=True)
(dependency / 'package.json').write_text(json.dumps({'name': 'goi_gpl_gia_lap', 'version': '1.0.0', 'license': 'GPL-3.0-only'}), encoding='utf-8')
(audit_directory / 'requirements.txt').write_text('MediaCrawler[extra]==1.0\n', encoding='utf-8')
audit = context['run_audit'](str(audit_directory))
assert audit['gate_passed'] and audit['unapproved_licenses_detected'] == audit['banned_packages_detected'] == 0
results['audit_gói_giả_lập'] = audit
results['thư_mục_fixture'] = str(temporary)
files = ['src/modules/staging_reliability/downstream_executor.py', 'src/modules/staging_reliability/budget_guard.py', 'src/modules/staging_reliability/prompt_regression.py', 'src/modules/staging_reliability/router.py', 'scripts/backup_staging_db.py', 'scripts/restore_staging_db.py', 'scripts/audit_licenses_and_deps.py', 'src/models/entities.py', 'src/schemas/contracts.py', 'docs/RELEASE_READINESS.md']
results['hash_mã_đối_chiếu'] = {f: hashlib.sha256((API / f).read_bytes()).hexdigest() for f in files}
output = ROOT / '08_kiem_thu/bang_chung/tai_hien_loi_p12_2026_10_21.json'
output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
print('Đã tái hiện và lưu bằng chứng P12:', output)
print('Số nhóm tình huống có assert:', len(results) - 3)
