"""Auto Edit không decode âm thanh ở host local khi bật worker từ xa."""
import pytest
from src.modules.dieu_phoi_dung import phat_hien_khoang_nghi as audio


def test_phan_tich_duoc_gui_ra_worker_khong_chay_ffmpeg_local(monkeypatch,tmp_path):
    from src.modules.tac_vu_tu_xa import client
    monkeypatch.setenv('REMOTE_COMPUTE_MODE','github')
    monkeypatch.delenv('REMOTE_ENGINE_CHILD',raising=False)
    path=tmp_path/'nguon.wav'
    path.write_bytes(b'chi de kiem tra chuyen task')
    expected={'pause_intervals':[[1000,3000]],'waveform_peaks':[0,25]}
    def execute(stage,operation,arguments,inputs,output=None):
        assert (stage,operation)==('QC','analyze_source_audio')
        assert arguments=={'audio_path':{'remote_input':0}} and inputs==[path]
        return expected
    monkeypatch.setattr(client,'execute',execute)
    monkeypatch.setattr(audio,'phat_hien_khoang_nghi',lambda *_: pytest.fail('Decode local'))
    monkeypatch.setattr(audio,'tinh_muc_song',lambda *_: pytest.fail('Đọc waveform local'))
    assert audio.phan_tich_am_thanh_nguon(path)==expected


def test_worker_thuc_thi_dung_bo_phan_tich_duoc_cho_phep(monkeypatch,tmp_path):
    from src.modules.tac_vu_tu_xa.stages import execute_stage
    monkeypatch.setenv('REMOTE_ENGINE_CHILD','1')
    path=tmp_path/'nguon.wav'
    monkeypatch.setattr(audio,'phat_hien_khoang_nghi',lambda p: [(1000,3000)] if p==path else pytest.fail('Sai input'))
    monkeypatch.setattr(audio,'tinh_muc_song',lambda p: [0,25] if p==path else pytest.fail('Sai input'))
    result=execute_stage({'stage':'QC','parameters':{'operation':'analyze_source_audio',
                          'arguments':{'audio_path':{'remote_input':0}}}},[path],tmp_path/'unused')
    assert result=={'pause_intervals':[(1000,3000)],'waveform_peaks':[0,25]}
