import hashlib
import importlib.util
import json
from pathlib import Path
import pytest


def load_script():
    path=Path(__file__).resolve().parents[2]/'ha_tang/chay_dev_local/chay_lo_auto_edit_da_duyet.py'
    spec=importlib.util.spec_from_file_location('chay_lo_auto_edit_da_duyet_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_mac_dinh_chi_kiem_tra_khong_tao_receipt_hoac_gui_lo(tmp_path,capsys):
    module=load_script()
    path=tmp_path/'goi.json'
    data={'state':'AWAITING_APPROVAL','plan':{'clips':[{} for _ in range(8)]},
          'visual_briefs':[{'renderer':'FLOW'}],'words':[{'text':'nguồn'}]}
    encoded=json.dumps(data).encode();path.write_bytes(encoded)
    path.with_suffix('.sha256').write_text(hashlib.sha256(encoded).hexdigest())
    module.main(['--bundle',str(path)])
    assert json.loads(capsys.readouterr().out)['approved'] is False
    assert sorted(p.name for p in tmp_path.iterdir())==['goi.json','goi.sha256']


def test_goi_bi_sua_sau_dong_bang_khong_duoc_chay(tmp_path):
    module=load_script()
    path=tmp_path/'goi.json';path.write_text('{}')
    path.with_suffix('.sha256').write_text('khong_khop')
    with pytest.raises(ValueError,match='đã thay đổi'):
        module.main(['--bundle',str(path),'--duyet'])
