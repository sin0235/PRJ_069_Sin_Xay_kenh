import json
from types import SimpleNamespace
from src.modules.dieu_phoi_dung.dung_video_dai import ClipTuDong,tao_y_tuong_dien_hoa_flow


def test_feedback_schema_chi_dung_layout_cua_canh_loi():
    clip=ClipTuDong(clip_id='clip',start_ms=0,end_ms=12000,title='Một ý',reason='Đủ ý')
    words=[{'id':'w1','text':'một ý rõ ràng','start_ms':0,'end_ms':3500},
           {'id':'w2','text':'đâu là lợi nhuận','start_ms':5000,'end_ms':8500}]
    class Client:
        max_output_tokens=4000
        calls=0
        def complete(self,messages,**kwargs):
            self.calls+=1
            if self.calls>1:
                feedback=json.loads(messages[1]['content'])['validator_feedback']
                assert 'OPEN_QUESTION:' in feedback and 'KINETIC_TITLE:' not in feedback
                return SimpleNamespace(content='{"visuals":[]}')
            def visual(word,layout,diagram):
                return {'clip_id':'clip','renderer':'HYPERFRAMES','start_word_id':word,'end_word_id':word,
                        'scene':'Thẻ giấy nhấn ý trong lời nói','action':'Chữ hiện theo nhịp',
                        'ui_scene':{'layout':layout,'diagram':diagram}}
            return SimpleNamespace(content=json.dumps({'visuals':[
                visual('w1','KINETIC_TITLE',{'title':'Một ý rõ ràng','on':{}}),
                visual('w2','OPEN_QUESTION',{'title':'Đâu là lợi nhuận','caption':'lợi nhuận','on':{'ask':'đâu là lợi nhuận'}}),
            ]}))
    client=Client()
    result=tao_y_tuong_dien_hoa_flow([clip],words,[],client,flow_available=False)
    assert result and client.calls>=2
