from src.config import read_llm_api_key_file


def test_doc_api_key_tu_dinh_dang_9rt_env(tmp_path):
    key_file = tmp_path / "9rt.env"
    key_file.write_text("base_url=https://gateway.example/v1\napi-key=sample-key-123\n", encoding="utf-8")

    assert read_llm_api_key_file(key_file) == "sample-key-123"


def test_doc_api_key_tu_dinh_dang_mot_dong(tmp_path):
    key_file = tmp_path / "llm_key"
    key_file.write_text("sample-key-123\n", encoding="utf-8")

    assert read_llm_api_key_file(key_file) == "sample-key-123"
