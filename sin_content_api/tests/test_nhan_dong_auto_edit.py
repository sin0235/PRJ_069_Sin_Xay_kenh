"""Nhãn Auto Edit đi qua schema và renderer ASS, giữ karaoke hệ thống."""
from src.modules.media_studio.ass_captions import build_karaoke_ass
from src.schemas.contracts import TimelineCaption


def test_nhan_dong_giu_co_qua_schema_va_xuat_hieu_ung_ass():
    label = TimelineCaption.model_validate({
        'text':'Doanh thu và tiền thực nhận','start_ms':1000,'duration_ms':2200,
        'font_size':72,'position_y_px':170,'animated_label':True,
    })
    assert label.model_dump()['animated_label'] is True
    ass = build_karaoke_ass([label],1080,1920)
    assert 'Dialogue: 1,0:00:01.00,0:00:03.20' in ass
    assert r'\move(540,194,540,170,0,180)' in ass
    assert r'\fs72' in ass and r'\t(0,180,\fscx100\fscy100)' in ass
    assert r'\1c&H006AB2D9&' in ass and r'\1c&H00FFFFFF&' in ass


def test_phu_de_cu_khong_tu_bien_thanh_nhan_dong():
    ass = build_karaoke_ass([{'text':'Lời nói','start_ms':0,'duration_ms':1000}],1080,1920)
    assert 'Dialogue: 0,' in ass and r'\move(' not in ass


def test_auto_edit_gui_tieu_de_va_tu_nhan_llm_vao_nhan_dong():
    from src.modules.dieu_phoi_dung.dung_video_dai import ClipTuDong, _caption_track
    clip = ClipTuDong(clip_id='nhan',start_ms=0,end_ms=6000,title='Nội dung',reason='Đủ ý',callout_word_ids=['w1'])
    captions = _caption_track(clip,[{'id':'w1','text':'tiền lời','start_ms':3000,'end_ms':4000}],[])
    labels = [c for c in captions if c.get('animated_label')]
    assert [c['text'] for c in labels] == ['Nội dung','tiền lời']
    assert [c['font_size'] for c in labels] == [72,70]
    assert any(c.get('words') and not c.get('animated_label') for c in captions)


def test_renderer_nhan_dong_hien_chuyen_dong_va_bien_mat_dung_cue(tmp_path):
    import subprocess
    from src.modules.media_studio.video_processor import video_processor

    def ffmpeg(*args):
        return subprocess.run(['ffmpeg','-v','error',*map(str,args)],check=True,capture_output=True).stdout

    source,output = tmp_path/'nguon.mp4',tmp_path/'ket_qua.mp4'
    ffmpeg('-y','-f','lavfi','-i','color=black:s=160x284:r=20:d=2','-threads','1',source)
    timeline = {'width':160,'height':284,'fps':20,
                'clips':[{'clip_id':'nguon','asset_id':'nguon','media_type':'video','start_ms':0,
                          'duration_ms':2000,'trim_in_ms':0,'trim_out_ms':2000}],
                'captions':[{'text':'TIỀN THỰC NHẬN','start_ms':500,'duration_ms':900,
                             'font_size':72,'position_y_px':170,'animated_label':True}]}
    video_processor.render_timeline_document(timeline,lambda _:source,output,caption_style='vietsub_karaoke_v2')

    def frame(t):
        return ffmpeg('-ss',t,'-i',output,'-vf','crop=160:100:0:0','-frames:v','1','-pix_fmt','gray','-f','rawvideo','-')

    assert max(frame(.1)) < 20
    assert sum(p>100 for p in frame(.8)) > 50
    assert frame(.55) != frame(.8)
    assert max(frame(1.8)) < 20
