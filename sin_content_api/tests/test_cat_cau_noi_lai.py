import pytest
from pydantic import ValidationError
from src.modules.dieu_phoi_dung.dung_video_dai import ClipTuDong, _cut_intervals, _caption_track, _kept_ranges


def test_khoang_giu_lai_khong_bi_cac_khoang_cat_ngoai_doan_keo_dai():
    assert _kept_ranges(10000,15000,[(2000,5000),(18000,20000)])==[(10000,15000)]


def test_doan_noi_lai_bi_bo_khong_tao_khoang_thieu_dien_hoa():
    from src.modules.dieu_phoi_dung.dung_video_dai import _storyboard_visual_gaps
    clip=ClipTuDong(clip_id='kb',title='Chi phí',reason='Giữ bản đọc sau',start_ms=0,end_ms=60000,
        retake_cuts=[{'start_ms':20000,'end_ms':40000,'reason':'Đọc lại'}])
    assert _storyboard_visual_gaps(clip,[],[])==[(0,20000),(40000,60000)]
    segment=clip.model_copy(update={'end_ms':10000})
    assert _storyboard_visual_gaps(segment,[],[])==[(0,10000)]


def test_cat_cau_noi_lai_va_phu_de_dung_cung_khoang_nguon():
    clip=ClipTuDong(clip_id='kb',title='Chi phí',reason='Giữ bản đọc sau',start_ms=0,end_ms=12000,
        retake_cuts=[{'start_ms':2000,'end_ms':4000,'reason':'Đọc lại cùng câu'}])
    words=[{'id':'w0','text':'Giữ đầu','start_ms':0,'end_ms':1000},
           {'id':'w1','text':'Đọc sai','start_ms':2500,'end_ms':3500},
           {'id':'w2','text':'Đọc đúng','start_ms':4500,'end_ms':5500}]
    cuts=_cut_intervals(clip,words,[(2500,5000)])
    assert cuts==[(2000,4875)]
    captions=_caption_track(clip,words,_cut_intervals(clip,words))
    spoken=[word for caption in captions for word in caption.get('words',[])]
    assert all(word['text']!='Đọc sai' for word in spoken)
    assert any(word['text']=='Đọc đúng' and word['start_ms']==2500 for word in spoken)


@pytest.mark.parametrize('start,end',[(900,1500),(2000,13000),(3000,2000)])
def test_tu_choi_khoang_cat_noi_lai_sai_ranh_gioi(start,end):
    with pytest.raises(ValidationError):
        ClipTuDong(clip_id='kb',title='Chi phí',reason='Giữ ý',start_ms=1000,end_ms=12000,
            retake_cuts=[{'start_ms':start,'end_ms':end,'reason':'Đọc lại'}])
