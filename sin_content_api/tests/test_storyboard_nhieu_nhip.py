"""Giữ cảnh hợp lệ qua nhiều lượt bổ sung cho một content dài."""
import json
from types import SimpleNamespace

from src.modules.dieu_phoi_dung.dung_video_dai import ClipTuDong, tao_y_tuong_dien_hoa_flow


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
