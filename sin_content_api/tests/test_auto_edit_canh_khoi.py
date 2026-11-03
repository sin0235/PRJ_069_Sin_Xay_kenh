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
