"""Không lấy thành phẩm hoặc cảnh AI làm nguồn dựng lại."""
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from src.modules.dieu_phoi_dung import bo_dinh_tuyen as router
from src.modules.dieu_phoi_dung.dung_video_dai import dung_video_dai


@pytest.mark.parametrize('product,parent', [('AUTO_EDIT',None),('AUTO_EDIT_HYPERFRAMES',None),
                                          ('GOOGLE_FLOW',None),('UPLOAD','nguon-cu')])
def test_api_va_worker_tu_choi_nguon_da_dung(monkeypatch,product,parent):
    source=SimpleNamespace(id='source',mime_detected='video/mp4',project_id='project',
                           source_product=product,parent_asset_id=parent)
    db=SimpleNamespace(query=lambda *_:SimpleNamespace(filter=lambda *_:SimpleNamespace(first=lambda:source)))
    monkeypatch.setattr(router,'_kiem_tra_quyen_du_an',lambda *_:SimpleNamespace(workflow_type='AUTO_EDIT'))
    monkeypatch.setattr(router.LLMClient,'from_db',lambda *_:pytest.fail('Không được gọi LLM với nguồn đã dựng'))
    with pytest.raises(HTTPException) as error:
        router.tu_dong_dung_video_dai('project',router.TaoVideoDaiRequest(source_asset_id='source',idempotency_key='source-test'),
                                    db,SimpleNamespace(workspace_id='ws',user_id='user'))
    assert error.value.status_code==409
    assert error.value.detail['error_code']=='AUTO_EDIT_ORIGINAL_SOURCE_REQUIRED'
    with pytest.raises(ValueError,match='AUTO_EDIT_ORIGINAL_SOURCE_REQUIRED'):
        dung_video_dai.__wrapped__(db,source_asset_id='source',workspace_id='ws',user_id='user',project_id='project')
