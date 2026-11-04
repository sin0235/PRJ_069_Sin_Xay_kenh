from src.modules.dieu_phoi_dung import dung_video_dai as editor


def test_bo_sung_chi_trong_khoang_thieu_va_khong_lap_lai(monkeypatch):
    clip=editor.ClipTuDong(clip_id='clip',start_ms=0,end_ms=30000,title='Một ý',reason='Đủ ý')
    words=[{'id':'w1','text':'mở đầu','start_ms':0,'end_ms':5000},
           {'id':'w2','text':'ý cần giải thích','start_ms':20000,'end_ms':25000}]
    first={'clip_id':'clip','start_word_id':'w1','end_word_id':'w1','renderer':'FLOW',
           'scene':'Đạo cụ giấy mở đầu','action':'Giấy chuyển động'}
    added={**first,'start_word_id':'w2','end_word_id':'w2'}
    calls=[]
    def plan(clips,*args,**kwargs):
        calls.append((clips[0].start_ms,clips[0].end_ms))
        return [added,first]
    monkeypatch.setattr(editor,'tao_y_tuong_dien_hoa_flow',plan)
    repair=getattr(editor,'bo_sung_khoang_dien_hoa',None)
    assert callable(repair)
    result=repair([clip],words,[first],[],object(),True)
    assert calls==[(5000,30000)]
    assert result==[first,added]
    assert repair([clip],words,result,[],object(),True)==result
    assert len(calls)==1
