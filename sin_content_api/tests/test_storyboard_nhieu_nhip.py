"""Giữ cảnh hợp lệ qua nhiều lượt bổ sung cho một content dài."""
import json
import pytest
from types import SimpleNamespace

from src.modules.dieu_phoi_dung.dung_video_dai import ClipTuDong, tao_y_tuong_dien_hoa_flow


def test_storyboard_nhan_ca_loi_thoai_cuoi_clip():
    clip = ClipTuDong(clip_id='cuoi', start_ms=0, end_ms=29000, title='Đủ nội dung', reason='Đủ ý')
    words = [{'id':f'w{i}', 'text':'nội dung giải thích', 'start_ms':i*80, 'end_ms':i*80+70}
             for i in range(200)]

    class Client:
        max_output_tokens = 4000
        max_input_bytes = 60000

        def complete(self, messages, **kwargs):
            transcript = json.loads(messages[1]['content'])['clips'][0]['transcript']
            assert 'w199[15920-15990]=' in transcript
            return SimpleNamespace(content='{"visuals":[]}')

    tao_y_tuong_dien_hoa_flow([clip], words, [], Client())


def test_clip_hai_phut_bo_sung_duoc_sau_canh_thu_ba():
    clip = ClipTuDong(clip_id='clip_dai', start_ms=0, end_ms=120000, title='Một câu chuyện', reason='Đủ ý')
    words = [{'id':f'w{i}', 'text':f'ý thứ {i}', 'start_ms':start, 'end_ms':start+5000}
             for i,start in enumerate([10000,30000,50000,70000,90000,110000])]

    def visual(i):
        return {'clip_id':clip.clip_id,'renderer':'FLOW','start_word_id':f'w{i}','end_word_id':f'w{i}',
                'scene':f'Đạo cụ giấy kể ý thứ {i}','action':f'Đạo cụ chuyển động làm rõ nguyên nhân và kết quả ý thứ {i}'}

    class Client:
        max_output_tokens = 4000

        def __init__(self):
            self.replies = iter([[visual(0),visual(2),visual(4)],[visual(1)],[visual(3)],[visual(5)]])
            self.calls = 0

        def complete(self, messages, **kwargs):
            self.calls += 1
            request = json.loads(messages[1]['content'])
            assert request['schema']['properties']['visuals']['maxItems'] == 3
            if self.calls > 1:
                assert request['visuals_hop_le_can_giu']
            return SimpleNamespace(content=json.dumps({'visuals':next(self.replies)},ensure_ascii=False))

    client = Client()
    result = tao_y_tuong_dien_hoa_flow([clip],words,[],client)
    assert [item['start_word_id'] for item in result] == [f'w{i}' for i in range(6)]
    assert client.calls == 4
    assert not clip.needs_review


def test_canh_khong_chong_lan_duoc_sap_theo_moc_loi():
    clip = ClipTuDong(clip_id='thu_tu', start_ms=0, end_ms=20000, title='Hai ý', reason='Đủ ý')
    words = [{'id':'dau','text':'ý đầu','start_ms':1000,'end_ms':5000},
             {'id':'cuoi','text':'ý cuối','start_ms':12000,'end_ms':16000}]

    class Client:
        max_output_tokens = 4000

        def complete(self, messages, **kwargs):
            return SimpleNamespace(content=json.dumps({'visuals':[
                {'clip_id':clip.clip_id,'renderer':'FLOW','start_word_id':i,'end_word_id':i,
                 'scene':'Vật thể giấy minh họa','action':'Giấy mở và gấp để làm rõ ý'}
                for i in ['cuoi','dau']
            ]},ensure_ascii=False))

    result = tao_y_tuong_dien_hoa_flow([clip],words,[],Client())
    assert [item['start_word_id'] for item in result] == ['dau','cuoi']
    assert not clip.needs_review


def test_moi_kich_ban_duoc_llm_lap_storyboard_rieng_khong_bo_clip_cuoi():
    clips = [ClipTuDong(clip_id=f'c{i}', start_ms=i*20000, end_ms=(i+1)*20000,
                       title=f'Kịch bản {i}', reason='Đủ ý') for i in range(21)]
    words = [{'id':f'w{i}','text':f'Nội dung {i}','start_ms':i*20000+1000,'end_ms':i*20000+5000}
             for i in range(21)]

    class Client:
        max_output_tokens = 4000
        calls = 0

        def complete(self, messages, **kwargs):
            request = json.loads(messages[1]['content'])
            assert len(request['clips']) == 1
            i = self.calls
            assert request['clips'][0]['clip_id'] == f'c{i}'
            self.calls += 1
            return SimpleNamespace(content=json.dumps({'visuals':[{
                'clip_id':f'c{i}','renderer':'FLOW','start_word_id':f'w{i}','end_word_id':f'w{i}',
                'scene':'Đạo cụ giấy minh họa','action':'Đạo cụ mở ra rồi gấp lại theo lời kể'
            }]},ensure_ascii=False))

    client = Client()
    result = tao_y_tuong_dien_hoa_flow(clips,words,[],client)
    assert client.calls == 21
    assert [item['clip_id'] for item in result] == [c.clip_id for c in clips]


@pytest.mark.parametrize(('count','error'), [(21,'VIDEO_SOURCE_NOT_FOUND'),(2001,'AUTO_EDIT_FLOW_JOBS_INVALID')])
def test_render_nhan_nhieu_clip_nhung_van_chan_danh_sach_vuot_gioi_han(count,error):
    from src.modules.dieu_phoi_dung.dung_video_dai import dung_video_dai

    query = SimpleNamespace(filter=lambda *_: SimpleNamespace(first=lambda: None))
    db = SimpleNamespace(query=lambda *_: query)
    with pytest.raises(ValueError,match=error):
        dung_video_dai(db,source_asset_id='nguon',workspace_id='workspace',user_id='user',project_id=None,
                      phase='render',flow_job_ids=[f'child{i}' for i in range(count)],plan_storage_key='plan.json')
