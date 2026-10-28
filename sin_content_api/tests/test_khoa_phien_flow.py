import subprocess
import sys
from pathlib import Path
import pytest

BRIDGE = Path(__file__).resolve().parents[2] / "cong_cu_tu_dong" / "flow_bridge"
sys.path.insert(0, str(BRIDGE))

def test_khoa_phien_doc_quyen_va_nha_sau_khi_tien_trinh_dung(tmp_path):
    from profile_guard import profile_lock, ProfileBusy
    profile = tmp_path / "tai_khoan_1"
    with profile_lock(profile):
        with pytest.raises(ProfileBusy), profile_lock(profile):
            pass
        with profile_lock(tmp_path / "tai_khoan_2"):
            pass
    script = "import sys,time; sys.path.insert(0,sys.argv[1]); from profile_guard import profile_lock; p=profile_lock(sys.argv[2]); p.__enter__(); print('READY', flush=True); time.sleep(60)"
    child = subprocess.Popen([sys.executable, "-c", script, str(BRIDGE), str(profile)], stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "READY"
        with pytest.raises(ProfileBusy), profile_lock(profile):
            pass
    finally:
        child.kill()
        child.wait(timeout=10)
    with profile_lock(profile):
        pass

def test_khoa_khong_xoa_du_lieu_chromium(tmp_path):
    from profile_guard import ensure_profile_free
    lock = tmp_path / "SingletonLock"
    lock.write_text("khong duoc xoa")
    ensure_profile_free(tmp_path)
    assert lock.read_text() == "khong duoc xoa"

def test_ham_duoc_bao_ve_khong_chay_khi_ho_so_ban(tmp_path):
    from profile_guard import profile_lock, profile_locked, ProfileBusy
    called = []
    @profile_locked(lambda: tmp_path)
    def task():
        called.append(True)
    with profile_lock(tmp_path):
        with pytest.raises(ProfileBusy):
            task()
    assert called == []
    task()
    assert called == [True]

@pytest.mark.parametrize("value", ["", "../outro", "a/b", "a b", ".", "é", "a" * 65])
def test_ten_ho_so_khong_hop_le(value):
    from profile_guard import validate_profile_id
    with pytest.raises(ValueError):
        validate_profile_id(value)

@pytest.mark.parametrize("value", ["mac_dinh", "tai-khoan-2", "A1"])
def test_ten_ho_so_hop_le(value):
    from profile_guard import validate_profile_id
    assert validate_profile_id(value) == value

def test_duong_dan_ho_so_tach_biet(tmp_path):
    from profile_guard import profile_dir_for
    assert profile_dir_for(tmp_path, "tai_khoan_1") == tmp_path / "tai_khoan_1"
    assert profile_dir_for(tmp_path, "tai_khoan_2") != profile_dir_for(tmp_path, "tai_khoan_1")
    with pytest.raises(ValueError):
        profile_dir_for(tmp_path, "../ngoai")

def test_cau_hinh_deploy_dung_cung_mot_ho_so(tmp_path):
    import os
    env = os.environ.copy()
    env.update(FLOW_PROFILE_ROOT=str(tmp_path / "profiles"), FLOW_PROFILE_ID="tai_khoan_2", MEDIA_ROOT_DIR=str(tmp_path / "media"))
    script = "import sys; sys.path.insert(0,sys.argv[1]); import config; print(config.BROWSER_PROFILE_DIR); print(config.LOCAL_BROWSER_PROFILE_DIR)"
    result = subprocess.run([sys.executable, "-c", script, str(BRIDGE)], env=env, text=True, capture_output=True, check=True)
    assert result.stdout.splitlines() == [str(tmp_path / "profiles" / "tai_khoan_2")] * 2

def test_nas_khong_bao_mo_cua_so_khi_khong_co_man_hinh(monkeypatch):
    from types import SimpleNamespace
    from fastapi import HTTPException
    from src.modules.media_studio import router
    monkeypatch.setenv("FLOW_PROFILE_ROOT", "/flow_profiles")
    monkeypatch.setattr(router.sys, "platform", "linux")
    tenant = SimpleNamespace(actor=SimpleNamespace(roles=[{"role_code": "WORKSPACE_OWNER", "scope_type": "WORKSPACE"}]))
    monkeypatch.setattr(router.subprocess, "Popen", lambda *_a, **_k: pytest.fail("Không được mở trình duyệt trong API NAS"))
    with pytest.raises(HTTPException) as exc:
        router.open_google_flow_login(tenant)
    assert exc.value.status_code == 503

def test_man_hinh_dang_nhap_giu_khoa_trong_luc_trinh_duyet_chay(tmp_path, monkeypatch):
    import importlib.util
    from profile_guard import profile_lock, ProfileBusy
    login_path = BRIDGE.parents[1] / "ha_tang" / "nas_flow_login" / "dang_nhap_flow.py"
    spec = importlib.util.spec_from_file_location("dang_nhap_flow_nas_test", login_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    profile = tmp_path / "tai_khoan_1"
    monkeypatch.setenv("FLOW_PROFILE_ROOT", str(tmp_path))
    monkeypatch.setenv("FLOW_PROFILE_ID", "tai_khoan_1")
    class FakePlaywright:
        def __enter__(self):
            from types import SimpleNamespace
            return SimpleNamespace(chromium=SimpleNamespace(executable_path="chromium"))
        def __exit__(self, *_args):
            pass
    monkeypatch.setattr(module, "sync_playwright", lambda: FakePlaywright())
    def run(_command):
        with pytest.raises(ProfileBusy), profile_lock(profile):
            pass
        return 0
    monkeypatch.setattr(module.subprocess, "call", run)
    with pytest.raises(SystemExit) as result:
        module.main()
    assert result.value.code == 0
    with profile_lock(profile):
        pass
