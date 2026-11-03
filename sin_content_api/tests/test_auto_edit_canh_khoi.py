"""Auto Edit dùng được các cảnh khối không có sự kiện diagram.on."""
import json
from types import SimpleNamespace
import pytest
from src.modules.dieu_phoi_dung.dung_video_dai import ClipTuDong, tao_y_tuong_dien_hoa_flow


@pytest.mark.parametrize('layout,fields',[
    ('KINETIC_TITLE',{'title':'Doanh thu chưa phải lợi nhuận'}),
    ('MARK_PHRASE',{'title':'Doanh thu chưa phải lợi nhuận','tag':'lợi nhuận'}),
    ('WORD_SWAP',{'title':'Cần kiểm tra','steps':['Giá bán','Giá vốn','Đóng gói']}),
    ('PILE_UP',{'title':'Chủ shop','value':'12'}),
    ('STAT_RING',{'title':'Tỷ lệ','to_value':60,'caption':'Đơn hoàn tất'}),
    ('CHART_STORY',{'title':'Doanh thu','labels':['Một','Hai','Ba'],
                    'series':[{'name':'Doanh thu','values':[10,20,30]}]}),
])
def test_auto_edit_nhan_canh_khoi_khong_co_moc_su_kien(layout,fields):
    clip=ClipTuDong(clip_id='clip',start_ms=0,end_ms=6000,title='Một ý',reason='Đủ ý')
    words=[{'id':'w1','text':'Doanh thu','start_ms':500,'end_ms':1500},
           {'id':'w2','text':'chưa phải','start_ms':2000,'end_ms':3000},
           {'id':'w3','text':'lợi nhuận','start_ms':3500,'end_ms':4500}]
    class Client:
        max_output_tokens=4000
        def complete(self,messages,**kwargs):
            return SimpleNamespace(content=json.dumps({'visuals':[{
                'clip_id':'clip','renderer':'HYPERFRAMES','start_word_id':'w1','end_word_id':'w3',
                'scene':'Thẻ giấy nhấn ý chính theo lời nói','action':'Chữ và khối giấy chuyển động',
                'ui_scene':{'layout':layout,'diagram':{**fields,'on':{}}},
            }]},ensure_ascii=False))
    result=tao_y_tuong_dien_hoa_flow([clip],words,[],Client(),flow_available=False)
    assert len(result)==1
    assert result[0]['ui_scene']['layout']==layout
    assert result[0]['duration_seconds']==4
    assert result[0]['target_start_word_id']=='w1'
    assert result[0]['target_end_word_id']=='w3'


def test_render_canh_khoi_dung_project_day_du_thay_vi_the_du_phong(tmp_path,monkeypatch):
    from src.modules.tao_video_noi_dung import render_engines, hf_project
    from src.modules.tao_video_noi_dung.planner import UiScene
    engines=tmp_path/'engines'
    cli=engines/'hyperframes/node_modules/hyperframes/bin/hyperframes.mjs'
    cli.parent.mkdir(parents=True);cli.write_text('')
    (engines/'vendor').mkdir();(engines/'vendor/gsap.min.js').write_text('')
    monkeypatch.setattr(render_engines,'engines_dir',lambda:engines)
    monkeypatch.setattr(render_engines,'_node',lambda:'node')
    monkeypatch.setattr(render_engines,'_chrome',lambda:None)
    calls=[]
    def build(out,shots,voice_wav,words,**kwargs):
        out.mkdir(exist_ok=True)
        calls.append((shots,kwargs))
    monkeypatch.setattr(hf_project,'build_project',build)
    def run(command,project,env):
        from pathlib import Path
        Path(command[command.index('-o')+1]).write_bytes(b'mov')
    monkeypatch.setattr(render_engines,'_run',run)
    monkeypatch.setattr(render_engines.video_processor,'probe_video',lambda _: {'has_alpha':True})
    scene=UiScene.model_validate({'layout':'KINETIC_TITLE','diagram':{'title':'Giữ đúng tiền lời','on':{}}})
    render_engines.render_hyperframes(scene,4,tmp_path/'scene.mov',narration='Giữ đúng tiền lời',aspect_ratio='9:16',transparent_background=True)
    assert len(calls)==1
    assert calls[0][0][0]['scene']==scene
    assert calls[0][1]['transparent_background'] is True
    assert calls[0][1]['transitions'] is False


@pytest.mark.parametrize('transparent',[False,True])
def test_nen_project_chi_trong_suot_khi_duoc_yeu_cau(tmp_path,transparent):
    from src.modules.tao_video_noi_dung import hf_project
    from src.modules.tao_video_noi_dung.planner import UiScene
    scene=UiScene.model_validate({'layout':'KINETIC_TITLE','diagram':{'title':'Giữ đúng tiền lời','on':{}}})
    info=hf_project.build_project(tmp_path/'project',[
        {'scene':scene,'seconds':4,'events':{},'narration':'Giữ đúng tiền lời'}],
        None,None,transitions=False,aspect_ratio='9:16',transparent_background=transparent)
    index=(tmp_path/'project/index.html').read_text(encoding='utf-8')
    assert ('<div id="bg"></div>' in index) is not transparent
    assert ('background:transparent' in index) is transparent
    assert info['native_scenes']==['KINETIC_TITLE'] and not info['legacy_scenes']
