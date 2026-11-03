"""Lưu audio nguồn theo hash để worker chạy lại không chuyển lại video lớn."""
import wave
from pathlib import Path
import pytest
from src.modules.dieu_phoi_dung import dung_video_dai as editor


def test_audio_da_tach_duoc_dung_lai_va_cache_hong_duoc_tao_lai(monkeypatch,tmp_path):
    from src.modules.tac_vu_tu_xa import stages
    monkeypatch.setattr(editor,'MEDIA_ROOT_DIR',tmp_path)
    calls=[]
    def extract(source,output):
        calls.append(source)
        with wave.open(str(output),'wb') as wav:
            wav.setparams((1,2,16000,0,'NONE','not compressed'))
            wav.writeframes(b'\0\0'*160)
    monkeypatch.setattr(stages,'extract_audio',extract)
    source=tmp_path/'nguon.mp4'
    path=editor.lay_am_thanh_nguon_da_tach(source,'a'*64)
    assert editor.lay_am_thanh_nguon_da_tach(source,'a'*64)==path
    assert calls==[source]
    path.write_bytes(b'file chua ghi xong')
    assert editor.lay_am_thanh_nguon_da_tach(source,'a'*64)==path
    assert calls==[source,source]
    editor.lay_am_thanh_nguon_da_tach(source,'b'*64)
    assert len(calls)==3


def test_tach_audio_that_bai_khong_de_lai_cache_do(monkeypatch,tmp_path):
    from src.modules.tac_vu_tu_xa import stages
    monkeypatch.setattr(editor,'MEDIA_ROOT_DIR',tmp_path)
    def fail(source,output):
        output.write_bytes(b'do')
        raise RuntimeError('EXTRACTION_FAILED')
    monkeypatch.setattr(stages,'extract_audio',fail)
    with pytest.raises(RuntimeError,match='EXTRACTION_FAILED'):
        editor.lay_am_thanh_nguon_da_tach(tmp_path/'nguon.mp4','a'*64)
    assert not list(tmp_path.rglob('*.wav'))
