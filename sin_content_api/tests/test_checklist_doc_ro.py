"""Kiểm chữ thực sự được xuất ra SVG, không chỉ cấu hình font."""
import json
import subprocess

from src.modules.tao_video_noi_dung.ui_sim import DIAGRAM_TEMPLATE


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
