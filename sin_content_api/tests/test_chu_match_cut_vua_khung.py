import json
import subprocess
from pathlib import Path
import pytest


@pytest.mark.parametrize('widths',[[1000,1400],[300,500]])
def test_match_cut_co_chu_theo_chieu_rong_thuc(widths):
    path=Path(__file__).parents[1]/'engines/hyperframes/blocks/text-match-cut.html'
    geometry=path.read_text(encoding='utf-8').split('// Geometry, measured at build time',1)[1].split('\n',1)[1].split('// One value curve.',1)[0]
    script='''
const root={clientWidth:1080,clientHeight:1920};
const copy=['A','B'];
const gsap={set:()=>{}};
const getComputedStyle=el=>({fontSize:el.style.fontSize||'100px'});
const texts=WIDTHS.map(width=>({style:{},querySelector:()=>({getBoundingClientRect:()=>({width})})}));
''' .replace('WIDTHS',json.dumps(widths))+geometry+'''
console.log(JSON.stringify({widths:natW,font:FS}));
'''
    result=json.loads(subprocess.run(['node','-e',script],capture_output=True,text=True,check=True).stdout)
    assert max(result['widths'])<=1080*.78+1
    if max(widths)<1080*.78:assert result['font']==100
