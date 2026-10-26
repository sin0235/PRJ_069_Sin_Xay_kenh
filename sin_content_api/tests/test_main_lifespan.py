from src import main


def test_e2e_test_worker_requires_explicit_flag_and_e2e_database(monkeypatch):
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("CONTENT_VIDEO_TEST_WORKER", "1")
    monkeypatch.setattr(main.settings, "app_env", "offline")
    monkeypatch.setattr(main.settings, "database_url", "sqlite:///./sin_content_e2e_test.db")

    assert main._e2e_test_worker_enabled()

    monkeypatch.setenv("CONTENT_VIDEO_TEST_WORKER", "0")
    assert not main._e2e_test_worker_enabled()

    monkeypatch.setenv("CONTENT_VIDEO_TEST_WORKER", "1")
    monkeypatch.setattr(main.settings, "database_url", "sqlite:///./sin_content.db")
    assert not main._e2e_test_worker_enabled()
