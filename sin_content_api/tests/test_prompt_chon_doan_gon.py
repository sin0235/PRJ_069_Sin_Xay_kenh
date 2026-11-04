import json
from types import SimpleNamespace
import pytest
from src.modules.dieu_phoi_dung.dung_video_dai import tao_ke_hoach_dung_video


def test_prompt_chon_doan_bo_xac_suat_nhung_khong_sua_du_lieu_asr():
    words=[{'id':'w1','text':'Một câu','start_ms':0,'end_ms':12000,'probability':0.123456789}]
    class Client:
        max_input_bytes=9000
        max_output_tokens=1200
        def complete(self,messages,**kwargs):
            payload=json.loads(messages[1]['content'])
            assert payload['tu_co_moc_thoi_gian']==[{
                'id':'w1','text':'Một câu','start_ms':0,'end_ms':12000}]
            return SimpleNamespace(content='{"clips":[]}')
    with pytest.raises(ValueError,match='NO_SOCIAL_CLIPS_SELECTED'):
        tao_ke_hoach_dung_video(words,Client(),12000)
    assert words[0]['probability']==0.123456789
