import copy
import subprocess
from pathlib import Path


def test_chi_gui_cua_so_nguon_va_dich_dong_bo_moc_hinh_tieng(tmp_path, monkeypatch):
    from src.modules.tac_vu_tu_xa import cua_so_nguon as module
    source=tmp_path/'nguon.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=s=108x192:r=30:d=6',
        '-f','lavfi','-i','sine=frequency=440:duration=6','-c:v','libx264','-threads','1','-g','30',
        '-pix_fmt','yuv420p','-c:a','aac',str(source)],check=True)
    args={'timeline':{'clips':[{'asset_id':'raw','audio_asset_id':'raw','trim_in_ms':2200,
        'trim_out_ms':4200,'audio_trim_in_ms':2200,'duration_ms':2000}]},'asset_paths':{'raw':{'remote_input':0}}}
    original=copy.deepcopy(args)
    monkeypatch.setattr(module,'MIN_WINDOW_BYTES',1)
    output=tmp_path/'cua_so';output.mkdir()
    shifted,inputs,proof=module.chuan_bi_cua_so(args,[source],output)
    assert args==original and inputs[0]!=source and inputs[0].is_file()
    offset=proof[0]['offset_ms'];clip=shifted['timeline']['clips'][0]
    assert clip['trim_in_ms']+offset==2200 and clip['trim_out_ms']+offset==4200
    assert clip['audio_trim_in_ms']==clip['trim_in_ms']
    assert proof[0]['packet_hash_verified'] and inputs[0].stat().st_size<source.stat().st_size


def test_offload_goi_bo_chuan_bi_truoc_khi_gui_renderer(tmp_path, monkeypatch):
    from src.modules.tac_vu_tu_xa import client, cua_so_nguon
    source=tmp_path/'nguon.mp4';source.write_bytes(b'nguon')
    proxy=tmp_path/'cua_so.mp4';proxy.write_bytes(b'cua so')
    monkeypatch.setattr(client,'enabled',lambda:True)
    def prepare(arguments,inputs,scratch):
        assert inputs==[source]
        return arguments,[proxy],[{'packet_hash_verified':True}]
    monkeypatch.setattr(cua_so_nguon,'chuan_bi_cua_so',prepare)
    def execute(stage,operation,arguments,inputs,output,input_windows=None):
        assert inputs==[proxy] and input_windows==[{'packet_hash_verified':True}]
        return {'ok':True}
    monkeypatch.setattr(client,'execute',execute)
    @client.offload('render_timeline','RENDER_FINAL',output='output_path')
    def render(timeline,asset_path_resolver,output_path):
        raise AssertionError('Không render nặng local')
    assert render({'clips':[{'asset_id':'raw'}]},lambda _:source,tmp_path/'out.mp4')=={'ok':True}
