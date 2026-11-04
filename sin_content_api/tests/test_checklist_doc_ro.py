"""Kiểm chữ thực sự được xuất ra SVG, không chỉ cấu hình font."""
import json
import subprocess

from src.modules.tao_video_noi_dung.ui_sim import DIAGRAM_TEMPLATE


def test_cau_hoi_giu_chu_thuong_mau_muc_tren_giay_sang():
    import re
    source = DIAGRAM_TEMPLATE.read_text(encoding='utf-8')
    function = source.split('function sceneOpenQuestion', 1)[1].split('/* ----------', 1)[0]
    script = '''
const COL={ink:'#f8f1df',coral:'#ED1B24'};
const eo=x=>x,seg=(t,a,b)=>Math.min(1,Math.max(0,(t-a)/(b-a)));
const tw=(s,fs)=>s.length*fs*.55,esc=s=>s;
''' + 'function sceneOpenQuestion' + function + '''
console.log(JSON.stringify(sceneOpenQuestion(6,{title:'Điều đáng hỏi: món nào đang nuôi cửa hàng?',caption:'Điều đáng hỏi',t:{ask:0,key:1}})));
'''
    result = subprocess.run(['node', '-e', script], capture_output=True, text=True, encoding='utf-8', check=True)
    text = re.findall(r'<text[^>]*fill="([^"]+)"[^>]*opacity="([^"]+)"[^>]*>(.*?)</text>', json.loads(result.stdout))
    assert any(color == '#163344' and word == 'món' for color, opacity, word in text)
    assert all(float(opacity) == 1 for color, opacity, word in text)


def test_checklist_toan_khung_them_dong_tu_tren_xuong_va_giu_dong_cu():
    from xml.etree import ElementTree
    source = DIAGRAM_TEMPLATE.read_text(encoding='utf-8')
    function = source.split('function sceneChecklist', 1)[1].split('/* ----------', 1)[0]
    script = '''
const PORTRAIT=true,TRANSPARENT_BG=false,W=1080;
const COL={tealD:'#083D70',tealL:'#5FA8FF',teal:'#0562AF',gold:'#FABC11',coral:'#ED1B24'};
const eo=x=>x,seg=(t,a,b)=>Math.min(1,Math.max(0,(t-a)/(b-a)));
const tw=(s,fs)=>s.length*fs*.55,fit=(s,w,fs)=>Math.min(fs,w/(s.length*.55));
const esc=s=>s,paperCard=()=>'',paperBadge=()=>'';
''' + 'function sceneChecklist' + function + '''
const p={steps:['Giá bán','Giá vốn','Lợi nhuận'],t:{c0:1,c1:2,c2:3}};
console.log(JSON.stringify([1.5,2.5,4].map(t=>sceneChecklist(t,p))));
'''
    result = subprocess.run(['node', '-e', script], capture_output=True, text=True, encoding='utf-8', check=True)
    visible = []
    for svg in json.loads(result.stdout):
        root = ElementTree.fromstring('<svg>' + svg + '</svg>')
        visible.append([text.text for group in root.findall('g') if float(group.get('opacity', '1')) == 1
                        for text in group.findall('text') if text.text in ['Giá bán','Giá vốn','Lợi nhuận']])
    assert visible == [['Giá bán'], ['Giá bán','Giá vốn'], ['Giá bán','Giá vốn','Lợi nhuận']]


def test_llm_khong_duoc_phong_the_thay_muc_thanh_checklist_toan_khung():
    from types import SimpleNamespace
    from src.modules.dieu_phoi_dung.dung_video_dai import ClipTuDong, chon_dien_hoa
    class Client:
        max_input_bytes, max_output_tokens, calls = 64000, 4000, 0
        def complete(self, messages, **kwargs):
            self.calls += 1
            return SimpleNamespace(content=json.dumps({'actions': [{
                'clip_id': 'clip', 'asset_id': 'the', 'mode': 'CUTAWAY' if self.calls == 1 else 'OVERLAY',
                'start_word_id': 'w1', 'end_word_id': 'w1', 'layout_position': 'upper_left',
                'layout_size': 'large', 'reason': 'Theo lời',
            }]}))
    client = Client()
    actions = chon_dien_hoa([ClipTuDong(clip_id='clip',start_ms=0,end_ms=5000,title='Chi phí',reason='Một ý')],
        [{'id':'w1','text':'giá bán','start_ms':1000,'end_ms':4000}], [{
            'asset_id':'the','target_clip_id':'clip','scene':'Thẻ từng mục','narration':'giá bán',
            'duration_seconds':3,'has_alpha':True,'width':1080,'height':1920,'aspect_ratio':'9:16',
            'renderer':'HYPERFRAMES','visual_kind':'diagram',
            'overlay_presentation':{'kind':'single_item_card','min_font_size_px':128},
        }], client)
    assert client.calls == 2 and actions[0]['mode'] == 'OVERLAY'


def test_the_checklist_alpha_khong_bi_camera_day_ra_khoi_canvas():
    source = DIAGRAM_TEMPLATE.read_text(encoding='utf-8')
    function = source.split('function setT(t)', 1)[1].split('window.setT =', 1)[0]
    script = '''
const PORTRAIT=true, TRANSPARENT_BG=true, W=1080,H=1920;
const P={kind:'CHECKLIST',dur:5,t:{},focus:{from:0,to:5,k:1.1,x:540,y:300},camera_motion:'AUTO'};
const eo=x=>x,eio=x=>x,seg=(t,a,b)=>Math.min(1,Math.max(0,(t-a)/(b-a))),clamp=x=>Math.max(0,Math.min(1,x));
const elements={},document={getElementById:id=>elements[id]||(elements[id]={style:{},setAttribute(k,v){this[k]=v},getAttribute(k){return this[k]}})};
const rig={style:{}},stage={style:{}},backSvg={style:{}},svg={style:{}},frontSvg={style:{}};
const pose={z:0,blur_px:0};
const window={__bahaCamera:{isLayered:()=>false,transform:()=>({origin:'50% 50%',transform:'scale(1.2)',perspective:1200,planes:{back:pose,middle:pose,front:pose}})}};
const SCENES={CHECKLIST:()=>''},caption=()=>'';
''' + 'function setT(t)' + function + '''
setT(4.3);
console.log(JSON.stringify({camera:elements.cam.transform,rig:rig.style.transform}));
'''
    result = subprocess.run(['node','-e',script],capture_output=True,text=True,check=True)
    transforms=json.loads(result.stdout)
    assert transforms == {'camera':'translate(0 0)','rig':'none'}


def test_checklist_alpha_doc_ro_khi_thu_xuong_405_px():
    source = DIAGRAM_TEMPLATE.read_text(encoding='utf-8')
    function = source.split('function sceneChecklist', 1)[1].split('/* ----------', 1)[0]
    script = '''
const PORTRAIT=true, TRANSPARENT_BG=true, W=1080;
const COL={tealD:'#083D70',tealL:'#5FA8FF',teal:'#0562AF',gold:'#FABC11',coral:'#ED1B24'};
const eo=x=>x, seg=(t,a,b)=>Math.min(1,Math.max(0,(t-a)/(b-a)));
const tw=(s,fs)=>s.length*fs*.55, fit=(s,w,fs)=>Math.min(fs,w/(s.length*.55));
const esc=s=>s, paperCard=()=>'', paperBadge=()=>'';
''' + 'function sceneChecklist' + function + '''
console.log(JSON.stringify(sceneChecklist(5, {steps:['giá bán','phân bổ và đóng gói'],t:{c0:0,c1:1}})));
'''
    result = subprocess.run(['node', '-e', script], capture_output=True, text=True, encoding='utf-8', check=True)
    svg = json.loads(result.stdout)
    import re
    font_sizes = [float(value) for value in re.findall(r'<text[^>]*data-role="item-label"[^>]*font-size="([0-9.]+)"', svg)]
    assert font_sizes and min(font_sizes) * 405 / 1080 >= 48
    displayed_text = ' '.join(re.findall(r'<text[^>]*>(.*?)</text>', svg))
    assert 'phân bổ và đóng gói' in displayed_text
    assert 'giá bán' not in displayed_text


def test_llm_nhan_duoc_kieu_the_alpha_va_co_chu_thuc():
    from types import SimpleNamespace
    from src.modules.dieu_phoi_dung.dung_video_dai import ClipTuDong, chon_dien_hoa

    presentation = {'kind':'single_item_card','min_font_size_px':128}

    class Client:
        max_input_bytes = 64000
        max_output_tokens = 4000

        def complete(self, messages, **kwargs):
            payload = json.loads(messages[1]['content'])
            asset = payload['assets_dien_hoa_giay_cung_du_an'][0]
            assert asset['overlay_presentation'] == presentation
            return SimpleNamespace(content=json.dumps({'actions':[{
                'clip_id':'clip','asset_id':'the','mode':'OVERLAY','start_word_id':'w1','end_word_id':'w1',
                'layout_position':'upper_left','layout_size':'large','reason':'Một thẻ chữ lớn theo lời',
            }]}))

    clip = ClipTuDong(clip_id='clip',start_ms=0,end_ms=5000,title='Chi phí',reason='Một ý')
    actions = chon_dien_hoa([clip],[{'id':'w1','text':'giá bán','start_ms':1000,'end_ms':4000}],[{
        'asset_id':'the','scene':'Thẻ giấy hiện một mục mỗi cue','narration':'giá bán',
        'duration_seconds':3,'has_alpha':True,'width':1080,'height':1920,'aspect_ratio':'9:16',
        'renderer':'HYPERFRAMES','visual_kind':'diagram','overlay_presentation':presentation,
    }],Client())
    assert actions[0]['mode'] == 'OVERLAY' and actions[0]['layout_size'] == 'large'
def test_timeline_auto_edit_dung_karaoke_lon_cua_he_thong():
    from src.modules.dieu_phoi_dung.dung_video_dai import ClipTuDong, _tao_timeline
    from src.schemas.contracts import KaraokeCaptionSettings

    clip = ClipTuDong(clip_id="karaoke", start_ms=0, end_ms=10000, title="Nội dung", reason="Đủ ý")
    timeline = _tao_timeline("nguon", clip, [{"id":"w1","text":"Nội dung","start_ms":0,"end_ms":1000}])
    settings = KaraokeCaptionSettings.model_validate(timeline["karaoke_settings"])
    assert settings.font_size == 70 and settings.layout == "two_line"
    assert settings.word_pop and settings.outline and settings.shadow
    assert settings.accent_color == "champagne"

