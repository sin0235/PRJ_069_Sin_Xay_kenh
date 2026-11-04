import time
import uuid
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.modules.tac_vu_tu_xa.service import TaskStore


def test_hai_luong_chay_dong_thoi_nhung_moi_luong_chi_mot_task(tmp_path):
    store=TaskStore(tmp_path/'tasks.db',tmp_path/'outputs')
    ai=store.create('QC',{},[],'ws','AI_VIDEO')
    edit=store.create('QC',{},[],'ws','AUTO_EDIT')
    store.create('QC',{},[],'ws','AUTO_EDIT')
    assert store.claim('ai',pipeline='AI_VIDEO')[0]['id']==ai
    assert store.claim('edit',pipeline='AUTO_EDIT')[0]['id']==edit
    assert store.claim('edit2',pipeline='AUTO_EDIT') is None
    assert store.get(ai)['state']=='RUNNING'


def test_session_legacy_va_pool_moi_khong_nhan_nham_task(tmp_path,monkeypatch):
    from src.modules.tac_vu_tu_xa import router
    store=TaskStore(tmp_path/'tasks.db',tmp_path/'outputs')
    legacy,new=str(uuid.uuid4()),str(uuid.uuid4())
    with store.connect() as db:
        db.execute('INSERT INTO runner_session(id,session_id,run_id,updated,ready) VALUES(1,?,?,?,1)',(legacy,'101',time.time()))
        db.execute('INSERT INTO runner_pools(pipeline,session_id,run_id,updated,ready) VALUES(?,?,?,?,1)',('AUTO_EDIT',new,'102',time.time()))
    ai=store.create('QC',{},[],'ws','AI_VIDEO');edit=store.create('QC',{},[],'ws','AUTO_EDIT')
    monkeypatch.setenv('REMOTE_COMPUTE_MODE','github')
    monkeypatch.setattr(router,'get_store',lambda:store)
    monkeypatch.setattr(router,'verify_oidc',lambda token:{'run_id':'101' if token=='ai' else '102'})
    app=FastAPI();app.include_router(router.router)
    with TestClient(app) as client:
        old=client.post('/v1/remote-tasks/claim',params={'session_id':legacy},headers={'Authorization':'Bearer ai'})
        new_response=client.post('/v1/remote-tasks/claim',params={'session_id':new},headers={'Authorization':'Bearer edit'})
        assert old.json()['task']['id']==ai and new_response.json()['task']['id']==edit
        rejected=client.post('/v1/remote-tasks/claim',params={'session_id':legacy},headers={'Authorization':'Bearer edit'})
        assert rejected.status_code==403
    store.heartbeat(edit,new_response.json()['token'])
    with store.connect() as db:
        assert db.execute('SELECT run_id FROM runner_session WHERE id=1').fetchone()[0]=='101'
        assert db.execute("SELECT ready FROM runner_pools WHERE pipeline='AUTO_EDIT'").fetchone()[0]==1


def test_tao_runner_auto_edit_khong_thay_session_ai_dang_chay(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from src.modules.tac_vu_tu_xa import client
    store=TaskStore(tmp_path/'tasks.db',tmp_path/'outputs')
    with store.connect() as db:
        db.execute("INSERT INTO runner_session(id,session_id,run_id,updated,ready) VALUES(1,'old','101',?,1)",(time.time(),))
    for key,value in {'REMOTE_GITHUB_REPOSITORY':'owner/repo','REMOTE_GITHUB_REF':'dev',
                      'REMOTE_PUBLIC_ORIGIN':'https://test.example','REMOTE_GITHUB_DISPATCH':'gh'}.items():
        monkeypatch.setenv(key,value)
    calls=[]
    def run(command,**kwargs):
        calls.append(command)
        assert command[1:3]==['workflow','run']
        return SimpleNamespace(returncode=0,stdout='https://github.com/owner/repo/actions/runs/102')
    monkeypatch.setattr(client.subprocess,'run',run)
    token=client.scope.set({'workspace':'ws','pipeline':'AUTO_EDIT'})
    try:client.ensure_runner(store)
    finally:client.scope.reset(token)
    with store.connect() as db:
        assert db.execute('SELECT run_id FROM runner_session WHERE id=1').fetchone()[0]=='101'
        assert db.execute("SELECT run_id FROM runner_pools WHERE pipeline='AUTO_EDIT'").fetchone()[0]=='102'
    assert 'pipeline=AUTO_EDIT' in calls[0]
