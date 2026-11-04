import importlib.util
from pathlib import Path


def test_xuat_clip_dau_khong_cho_canh_clip_sau():
    path=Path(__file__).resolve().parents[2]/'ha_tang/chay_dev_local/chay_lo_auto_edit_da_duyet.py'
    spec=importlib.util.spec_from_file_location('lo8',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    briefs=[{'target_clip_id':'kb_01'},{'target_clip_id':'kb_02'}]
    jobs=[{'index':0,'job_id':'done'},{'index':1,'job_id':'queued'}]
    def read(ids):
        assert ids==['done']
        return ['SUCCEEDED']
    module.cho_canh_clip('kb_01',briefs,jobs,read,sleep=lambda _: (_ for _ in ()).throw(AssertionError('Không được chờ clip sau')))
