"""Rà soát ngoại tuyến; chỉ dùng SQLite trong RAM, không sửa dữ liệu dự án."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone, timedelta

os.environ['DATABASE_URL'] = 'sqlite://'
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).parent))
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool
import src.database as database

database.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
@event.listens_for(database.engine, 'connect')
def foreign_keys(connection, record):
    connection.execute('PRAGMA foreign_keys=ON')
database.SessionLocal.configure(bind=database.engine)
from src.models.entities import *
from src.main import app
from src.api.deps import get_current_actor
from src.policy.evaluator import ActorContext, ResourceContext, evaluate_permission
from src.services.role_service import RoleService
from src.services.worker_service import WorkerAuthService
from src.services.approval_service import ApprovalService
from src.services.tenant_service import TenantService
from fastapi.testclient import TestClient
import pytest

root = Path(__file__).resolve().parents[2]
evidence = root / '08_kiem_thu' / 'bang_chung'
buffer = io.StringIO()
with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
    exit_code = pytest.main([str(Path(__file__).parent / 'tests'), '-q', '-p', 'no:cacheprovider'])
(evidence / 'kiem_thu_ra_soat_phan_quyen_2026_10_21.txt').write_text(
    'Môi trường: SQLite chỉ trong RAM; StaticPool; khóa ngoại bật.\n'
    'Lệnh: python 03_ban_lam_viec/baha_auth/ra_soat_phan_quyen_2026_10_21.py\n'
    + buffer.getvalue() + f'\nMã thoát pytest: {exit_code}\n', encoding='utf-8')

database.Base.metadata.drop_all(database.engine)
database.Base.metadata.create_all(database.engine)
db = database.SessionLocal()
db.add_all([Workspace(id='a', name='A', slug='a'), Workspace(id='b', name='B', slug='b')])
db.commit()
for name in ['owner', 'lead', 'staff', 'exec', 'foreign']:
    db.add(GlobalUser(id=name, email=name+'@example.invalid'))
db.commit()
for name in ['owner', 'lead', 'staff', 'exec', 'foreign']:
    db.add(Membership(id='m-'+name, workspace_id='b' if name=='foreign' else 'a', user_id=name))
for code in ['WORKSPACE_OWNER', 'TEAM_LEAD', 'RESEARCHER', 'EXECUTIVE']:
    db.add(Role(id=code, code=code, name=code, is_template=True))
db.commit()
for name, role, scope, scope_id in [('owner','WORKSPACE_OWNER','WORKSPACE',None), ('lead','TEAM_LEAD','TEAM','team-1'), ('staff','RESEARCHER','WORKSPACE',None), ('exec','EXECUTIVE','WORKSPACE',None)]:
    db.add(RoleAssignment(id='ra-'+name, workspace_id='a', membership_id='m-'+name, role_id=role, scope_type=scope, scope_id=scope_id))
db.add(BusinessResource(id='private', workspace_id='a', owner_id='owner', title='Riêng tư', search_text='bi_mat'))
db.commit()
client = TestClient(app)
def headers(user):
    return {'X-Workspace-Id':'a', 'X-User-Id':user}
results = {}
response = client.post('/authz/v1/org/units', headers=headers('owner'), json={'name':'Đơn vị giả danh'})
results['gia_danh_khong_co_token'] = {'status':response.status_code, 'da_ghi_du_lieu':db.query(OrgUnit).count()==1}
response = client.post('/authz/v1/assignments', headers=headers('lead'), json={'grantee_membership_id':'m-staff','role_code':'RESEARCHER','scope_type':'WORKSPACE'})
results['truong_nhom_cap_quyen_toan_workspace'] = {'status':response.status_code,'scope':response.json().get('scope_type')}
response = client.post('/authz/v1/assignments', headers=headers('owner'), json={'grantee_membership_id':'m-staff','role_code':'PLATFORM_OPS'})
results['owner_cap_vai_tro_nen_tang'] = {'status':response.status_code,'role':response.json().get('role_code')}
assignment = db.get(RoleAssignment, 'ra-exec')
assignment.valid_until = datetime.now(timezone.utc)-timedelta(days=1)
db.commit()
response = client.post('/authz/v1/org/units', headers=headers('exec'), json={'name':'Quyền đã hết hạn'})
results['vai_tro_het_han_van_ghi_duoc'] = {'status':response.status_code}
actor = ActorContext('staff','a','m-staff','ACTIVE',[],[],[])
results['khong_co_role_van_doc_sua'] = {'so_ban_ghi':len(TenantService.list_resources(db,actor)), 'sua_thanh_cong':TenantService.update_resource(db,actor,'private','Đã sửa trái quyền'), 'url':TenantService.get_asset_download_url(db,actor,'private')}
lead = ActorContext('lead','a','m-lead','ACTIVE',[{'role_code':'TEAM_LEAD','scope_type':'TEAM','scope_id':'team-1'}],[],['team-1','team-2'])
results['quyen_team_1_lan_sang_team_2'] = evaluate_permission(lead,'ideas.read',ResourceContext('a',org_unit_id='team-2')).allowed
owner_actor = ActorContext('owner','a','m-owner','ACTIVE',[{'role_code':'WORKSPACE_OWNER','scope_type':'WORKSPACE'}],[],[])
results['owner_khong_doc_duoc_vi_sai_action_key'] = TenantService.get_resource(db, owner_actor, 'private') is None
response = client.post('/authz/v1/evaluate', headers=headers('owner'), json={'action_key':'ideas.read','resource_id':'khong-ton-tai'})
results['tai_nguyen_khong_ton_tai_van_allow'] = response.json()
response = client.post('/authz/v1/workers/grants',headers=headers('owner'),json={'job_id':'job-a','target_resource':'tai-nguyen-khong-ton-tai','allowed_actions':['roles.assign','fake.action'],'expires_at':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()})
db.get(RoleAssignment,'ra-owner').status='REVOKED'
db.commit()
response = client.post('/authz/v1/workers/recheck',json={'job_id':'job-a','action_key':'fake.action'})
results['worker_khong_xac_thuc_sau_thu_hoi_role'] = response.json()
response = client.post('/authz/v1/approvals/runs',headers=headers('staff'),json={'artifact_type':'BRIEF','artifact_id':'private','artifact_version':1,'content_hash':'gia','stages':[{'stage_key':'DUYET','allowed_role':'PLATFORM_OPS'}]})
run_id = response.json()['id']
step_id = response.json()['steps'][0]['id']
results['nhan_vien_tu_dat_chinh_sach_duyet'] = {'status':response.status_code}
response = client.post('/authz/v1/approvals/decisions',headers=headers('exec'),json={'step_id':step_id,'result':'APPROVED','artifact_version':1,'content_hash':'gia'})
db.expire_all()
results['sai_vai_tro_duoc_duyet_va_loi_trang_thai'] = {'status':response.status_code,'step':db.get(ApprovalStep,step_id).status,'run':db.get(ApprovalRun,run_id).status}
response = client.post('/authz/v1/approvals/decisions',headers=headers('exec'),json={'step_id':step_id,'result':'APPROVED','artifact_version':1,'content_hash':'gia'})
results['gui_lai_quyet_dinh_sinh_trung'] = {'status':response.status_code,'so_quyet_dinh':db.query(ApprovalDecision).filter_by(step_id=step_id).count()}
db.add(OrgUnit(id='foreign-dept',workspace_id='b',name='Phòng B',type='DEPARTMENT'))
db.commit()
db.add(OrgAssignment(workspace_id='a',membership_id='m-staff',org_unit_id='foreign-dept'))
db.commit()
results['rang_buoc_db_cho_phep_gan_phong_khac_tenant'] = True
results['audit_cho_cac_thao_tac_quyen_va_duyet'] = {'tong_event':db.query(AuthorizationAuditEvent).count(),'event_cap_thu_hoi_duyet':db.query(AuthorizationAuditEvent).filter(AuthorizationAuditEvent.action_key.in_(['roles.assign','brief.approve'])).count()}
results['pytest_exit_code'] = int(exit_code)
(evidence/'tai_hien_loi_phan_quyen_2026_10_21.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(buffer.getvalue())
print(json.dumps(results,ensure_ascii=False,indent=2))
db.close()
