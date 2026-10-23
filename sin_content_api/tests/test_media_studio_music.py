# -*- coding: utf-8 -*-

"""Kiểm thử tự động Động cơ Âm nhạc AI & Xử lý Âm thanh Chuẩn TikTok (GF04 + P08/GF05).

Bao gồm trọn bộ 12 ca kiểm thử theo chuẩn GOOGLE_FLOW_ACCEPTANCE_CASES.json:

- GF04-01: Lyria 3 Clip 30s Offline Contract (Gemini API REST)

- GF04-02: Lyria Full-Song Offline Contract (lyria-3.5)

- GF04-03: Model / Region Unavailable (Không fallback ngụy tạo)

- GF04-04: Auto-Ducking Voice & Music Mix

- GF04-05: Rights & Impersonation Filter (Chặn nhái giọng nghệ sĩ)

- GF04-06: Prompt Safety Filtering (Provider safety filter block)

- GF04-07: Flow Pilot Region Blocked / Disabled

- GF04-08: Instrumental Mode Constraints

- GF04-09: True EBU R128 Measurement & Audio QC Pass/Fail

- GF04-10: Persistent Idempotency & Budget Preflight

- GF04-11: Separation of Duties Gate (Rào chắn Bốn Mắt duyệt asset)

- GF04-12: Session Revocation Fail-Closed (FLOW_LOGIN_REQUIRED)

- GF04-13: Capabilities Endpoint Probe

"""



import os

import sys

import uuid

import json

import time

import base64

import hmac

import hashlib

import pathlib

import subprocess

import httpx

import pytest

from fastapi.testclient import TestClient



TEST_DATABASE_URL = "sqlite:///file:music_test_db?mode=memory&cache=shared&uri=true"

os.environ["DATABASE_URL"] = TEST_DATABASE_URL

os.environ["BAHA_AUTH_DATABASE_URL"] = "sqlite:///file:music_auth_test_db?mode=memory&cache=shared&uri=true"

os.environ["BAHA_AUTH_JWT_SECRET"] = "secret-key-music-test-2026"

os.environ["BAHA_AUTH_JWT_ISSUER"] = "baha-auth-issuer"

os.environ["BAHA_AUTH_JWT_AUDIENCE"] = "baha-auth-audience"

os.environ["APP_ENV"] = "test"

os.environ["TESTING"] = "1"



PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]

API_ROOT = pathlib.Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:

    sys.path.insert(0, str(PROJECT_ROOT))

if str(API_ROOT) not in sys.path:

    sys.path.insert(0, str(API_ROOT))



from src.main import app

from src.database import Base, SessionLocal, engine

from baha_auth.src.database import Base as AuthBase, SessionLocal as AuthSessionLocal, engine as AuthEngine

from src.models.entities import Workspace, User, MediaAsset, AIGenerationJob, WorkspaceBudget

from baha_auth.src.models.entities import (

    GlobalUser, Membership as AuthMembership, Role as AuthRole,

    RoleAssignment, Workspace as AuthWorkspace

)

from src.modules.media_studio.audio_processor import audio_processor

from src.modules.media_studio.music_provider import (

    music_orchestrator,

    GoogleOfficialLyriaAdapter,

    LocalTestSynthAdapter,

    FlowBrowserPilotAdapter

)

from src.schemas.contracts import MusicProviderType, MusicGenerationMode



client = TestClient(app)





def tao_bearer_jwt(user_id: str) -> str:

    def b64url(val):

        raw = json.dumps(val, separators=(",", ":")).encode("utf-8")

        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")



    h = b64url({"alg": "HS256", "typ": "JWT"})

    c = b64url({

        "sub": user_id,

        "iss": os.environ["BAHA_AUTH_JWT_ISSUER"],

        "aud": os.environ["BAHA_AUTH_JWT_AUDIENCE"],

        "exp": int(time.time()) + 7200,

    })

    inp = f"{h}.{c}".encode("ascii")

    sig = hmac.new(os.environ["BAHA_AUTH_JWT_SECRET"].encode("utf-8"), inp, hashlib.sha256).digest()

    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode("ascii")

    return f"{h}.{c}.{sig_b64}"





@pytest.fixture(scope="module", autouse=True)

def setup_databases():

    Base.metadata.create_all(bind=engine)

    AuthBase.metadata.create_all(bind=AuthEngine)

    yield

    Base.metadata.drop_all(bind=engine)

    AuthBase.metadata.drop_all(bind=AuthEngine)





@pytest.fixture

def music_fixture(tmp_path):

    ws_id = f"ws-music-{uuid.uuid4().hex[:8]}"

    user_id = f"user-music-{uuid.uuid4().hex[:8]}"

    reviewer_id = f"user-reviewer-{uuid.uuid4().hex[:8]}"



    with SessionLocal() as db:

        ws = Workspace(id=ws_id, name="Music Studio WS", slug=f"ws-{uuid.uuid4().hex[:6]}")

        u = User(id=user_id, email=f"creator-{user_id}@baha.vn", hashed_password="mock")

        u2 = User(id=reviewer_id, email=f"reviewer-{reviewer_id}@baha.vn", hashed_password="mock")

        budget = WorkspaceBudget(workspace_id=ws_id, allocated_units=10.0, hard_limit_units=10.0, spent_units=0.0)

        db.add_all([ws, u, u2, budget])

        db.commit()



    with AuthSessionLocal() as auth_db:

        auth_ws = AuthWorkspace(id=ws_id, name="Music Studio WS", slug=ws_id, status="ACTIVE")

        gu = GlobalUser(id=user_id, email=f"creator-{user_id}@baha.vn", status="ACTIVE")

        gu2 = GlobalUser(id=reviewer_id, email=f"reviewer-{reviewer_id}@baha.vn", status="ACTIVE")

        auth_db.add_all([auth_ws, gu, gu2])

        auth_db.commit()



        m = AuthMembership(id=str(uuid.uuid4()), user_id=user_id, workspace_id=ws_id, status="ACTIVE")

        m2 = AuthMembership(id=str(uuid.uuid4()), user_id=reviewer_id, workspace_id=ws_id, status="ACTIVE")

        auth_db.add_all([m, m2])

        auth_db.commit()



        role_owner = auth_db.query(AuthRole).filter(AuthRole.code == "WORKSPACE_OWNER").first()

        if not role_owner:

            role_owner = AuthRole(code="WORKSPACE_OWNER", name="Workspace Owner", is_template=True, status="ACTIVE")

            auth_db.add(role_owner)

            auth_db.commit()



        ra = RoleAssignment(

            id=str(uuid.uuid4()), membership_id=m.id, role_id=role_owner.id,

            workspace_id=ws_id, status="ACTIVE", granted_by=m.id, scope_type="WORKSPACE"

        )

        ra2 = RoleAssignment(

            id=str(uuid.uuid4()), membership_id=m2.id, role_id=role_owner.id,

            workspace_id=ws_id, status="ACTIVE", granted_by=m2.id, scope_type="WORKSPACE"

        )

        auth_db.add_all([ra, ra2])

        auth_db.commit()



    # Sinh file âm thanh test bằng FFmpeg

    voice_file = tmp_path / "voice_sample.mp3"

    music_file = tmp_path / "music_sample.mp3"



    subprocess.run([

        audio_processor.ffmpeg_bin, "-y", "-f", "lavfi",

        "-i", "sine=frequency=300:duration=4", "-ar", "44100", "-b:a", "128k", str(voice_file)

    ], check=True, capture_output=True)



    subprocess.run([

        audio_processor.ffmpeg_bin, "-y", "-f", "lavfi",

        "-i", "sine=frequency=600:duration=8", "-ar", "44100", "-b:a", "128k", str(music_file)

    ], check=True, capture_output=True)



    # Sinh một đoạn audio hợp lệ 30s để làm payload giả lập

    mock_audio_file = tmp_path / "mock_30s.mp3"

    subprocess.run([

        audio_processor.ffmpeg_bin, "-y", "-f", "lavfi",

        "-i", "sine=frequency=440:duration=30", "-af", "loudnorm=I=-14:LRA=7:tp=-1.5",

        "-ar", "44100", "-b:a", "192k", str(mock_audio_file)

    ], check=True, capture_output=True)

    mock_audio_bytes = mock_audio_file.read_bytes()



    return {

        "ws_id": ws_id,

        "user_id": user_id,

        "reviewer_id": reviewer_id,

        "token": tao_bearer_jwt(user_id),

        "reviewer_token": tao_bearer_jwt(reviewer_id),

        "voice_file": voice_file,

        "music_file": music_file,

        "mock_audio_bytes": mock_audio_bytes,

        "tmp_dir": tmp_path

    }





# ==============================================================================

# GF04-01: Lyria 3 Clip 30s Offline Contract

# ==============================================================================

def test_gf04_01_lyria_clip_offline_contract(music_fixture):

    """GF04-01: Tạo clip Lyria 3 Clip 30s qua contract Gemini API Interactions REST (Header auth & JSON schema)."""

    b64_audio = base64.b64encode(music_fixture["mock_audio_bytes"]).decode("ascii")



    def mock_handler(request: httpx.Request):

        # 1. URL phải là /interactions, tuyệt đối KHÔNG chứa ?key= trong URL (Vấn đề 5)

        assert "/interactions" in str(request.url)

        assert "?key=" not in str(request.url)

        # 2. Key bắt buộc truyền qua HTTP Header x-goog-api-key (Vấn đề 5)

        assert request.headers.get("x-goog-api-key") == "mock-api-key-lyria-2026"



        req_json = json.loads(request.content.decode("utf-8"))

        assert req_json["model"] == "models/lyria-3-clip-preview"

        assert "input" in req_json



        # 3. Phản hồi theo chuẩn Interactions API (Vấn đề 1)

        body = {

            "id": "interaction-lyria-test-01",

            "status": "COMPLETED",

            "outputs": [

                {

                    "type": "audio",

                    "mime_type": "audio/mp3",

                    "data": b64_audio,

                    "metadata": {

                        "duration_seconds": 30.0,

                        "synthid_watermark": True

                    }

                },

                {

                    "type": "text",

                    "text": "[Verse] Hello world melody"

                }

            ],

            "usage": {

                "cost_usd": 0.03,

                "billing_units": 1

            }

        }

        return httpx.Response(200, json=body)



    mock_transport = httpx.MockTransport(mock_handler)

    adapter = GoogleOfficialLyriaAdapter(api_key="mock-api-key-lyria-2026")



    # Kiểm tra input duration_sec = 20 vẫn được quy chuẩn thành clip 30s hợp lệ (Vấn đề 7)

    res = adapter.generate(

        prompt="Giai điệu Acoustic vui tươi",

        genre="Acoustic",

        mood="Upbeat",

        duration_sec=20,

        model_id="lyria-3-clip-preview",

        workspace_id=music_fixture["ws_id"],

        client_transport=mock_transport

    )



    assert res["status"] == "SUCCEEDED"

    assert res["source_product"] == "GEMINI_LYRIA_OFFICIAL"

    assert res["model_id"] == "lyria-3-clip-preview"

    assert res["duration_ms"] == 30000

    assert res["watermark_synthid"] is True

    assert res["actual_cost"] == 0.03

    assert "[Verse]" in res["lyrics_metadata"]



    # Kiểm định Audio QC EBU R128 trên tệp sinh ra với dung sai chuẩn plan +- 1.0 LU (Vấn đề 7)

    qc = audio_processor.verify_audio_qc(

        pathlib.Path(res["storage_path"]),

        expected_duration_sec=30.0,

        target_lufs=-14.0,

        lufs_tolerance=1.0,

        max_true_peak_dbtp=-1.5

    )

    assert qc["passed"] is True

    assert -15.0 <= qc["measured_i_lufs"] <= -13.0


def test_gf04_clip_duration_is_validated_against_fixed_30_seconds(music_fixture, monkeypatch):
    audio_path = music_fixture["tmp_dir"] / "mock_30s.mp3"
    audio_bytes = audio_path.read_bytes()

    def fake_generate(**kwargs):
        assert kwargs["duration_sec"] == 20
        return {
            "storage_path": str(audio_path),
            "relative_storage_key": f"workspaces/{music_fixture['ws_id']}/media/clip.mp3",
            "filename": "clip.mp3",
            "sha256": hashlib.sha256(audio_bytes).hexdigest(),
            "byte_size": len(audio_bytes),
            "source_product": "GEMINI_LYRIA_OFFICIAL",
            "duration_ms": 30_000,
        }

    monkeypatch.setattr(music_orchestrator.lyria_adapter, "generate", fake_generate)
    with SessionLocal() as db:
        asset = music_orchestrator.generate_music_track(
            db=db,
            workspace_id=music_fixture["ws_id"],
            user_id=music_fixture["user_id"],
            prompt="Clip Lyria ngắn hơn thời lượng cố định",
            duration_sec=20,
            provider=MusicProviderType.GOOGLE_OFFICIAL,
            mode=MusicGenerationMode.CLIP_30S,
        )

    assert asset.duration_ms == 30_000





# ==============================================================================

# GF04-02: Lyria Full-Song Offline Contract (lyria-3.5)

# ==============================================================================

def test_gf04_02_lyria_full_song_offline_contract(music_fixture):

    """GF04-02: Tạo bài hát dài Lyria 3.5 qua contract Gemini API Interactions REST."""

    b64_audio = base64.b64encode(music_fixture["mock_audio_bytes"]).decode("ascii")



    def mock_handler(request: httpx.Request):

        assert "/interactions" in str(request.url)

        assert "?key=" not in str(request.url)

        assert request.headers.get("x-goog-api-key") == "mock-api-key-lyria-2026"



        req_json = json.loads(request.content.decode("utf-8"))

        assert req_json["model"] == "models/lyria-3.5"



        body = {

            "id": "interaction-lyria-test-02",

            "status": "COMPLETED",

            "outputs": [

                {

                    "type": "audio",

                    "mime_type": "audio/mp3",

                    "data": b64_audio,

                    "metadata": {

                        "duration_seconds": 60.0,

                        "synthid_watermark": True

                    }

                },

                {

                    "type": "text",

                    "text": "[Verse 1]\nMột ngày mới tràn đầy năng lượng\n[Chorus]\nBAHA Group vươn xa"

                }

            ],

            "usage": {

                "cost_usd": 0.08,

                "billing_units": 1

            }

        }

        return httpx.Response(200, json=body)



    mock_transport = httpx.MockTransport(mock_handler)

    adapter = GoogleOfficialLyriaAdapter(api_key="mock-api-key-lyria-2026")



    res = adapter.generate(

        prompt="Bài hát Pop hiện đại truyền cảm hứng",

        genre="Pop",

        mood="Inspirational",

        lyrics="[Verse 1]\nMột ngày mới tràn đầy năng lượng\n[Chorus]\nBAHA Group vươn xa",

        duration_sec=60,

        model_id="lyria-3.5",

        workspace_id=music_fixture["ws_id"],

        client_transport=mock_transport

    )



    assert res["status"] == "SUCCEEDED"

    assert res["model_id"] == "lyria-3.5"

    assert res["watermark_synthid"] is True

    assert res["actual_cost"] == 0.08

    assert "[Chorus]" in res["lyrics_metadata"]





# ==============================================================================

# GF04-03: Model / Region Unavailable (Không fallback ngụy tạo)

# ==============================================================================

def test_gf04_03_model_or_region_unavailable(music_fixture):

    """GF04-03: Báo lỗi MODEL_UNAVAILABLE / REGION_UNAVAILABLE rõ ràng, cấm tự sinh nhạc procedural."""

    def mock_handler(request: httpx.Request):

        return httpx.Response(404, json={"error": {"message": "Model lyria-experimental not found in your region"}})



    mock_transport = httpx.MockTransport(mock_handler)

    adapter = GoogleOfficialLyriaAdapter(api_key="mock-api-key-lyria-2026")



    with pytest.raises(RuntimeError, match="MODEL_UNAVAILABLE"):

        adapter.generate(

            prompt="Nhạc EDM",

            model_id="lyria-experimental",

            workspace_id=music_fixture["ws_id"],

            client_transport=mock_transport

        )





# ==============================================================================

# GF04-04: Auto-Ducking Voice & Music Mix

# ==============================================================================

def test_gf04_04_audio_ducking_voice_and_music_mix(music_fixture):

    """GF04-04: Tự động hạ nhạc nền (-18dB) khi có giọng đọc thuyết minh."""

    duck_out = music_fixture["tmp_dir"] / "gf04_ducked.mp3"

    meta = audio_processor.apply_auto_ducking(

        voice_path=music_fixture["voice_file"],

        music_path=music_fixture["music_file"],

        output_path=duck_out,

        music_attenuation_db=-18.0

    )

    assert duck_out.exists()

    assert duck_out.stat().st_size > 2000

    assert meta["ducking_applied"] is True



    # Đo ffprobe xác nhận codec và sample rate

    probe = audio_processor.probe_audio(duck_out)

    assert probe["codec_name"] == "mp3"

    assert probe["sample_rate_hz"] in (44100, 48000)





# ==============================================================================

# GF04-05: Rights & Impersonation Filter (Chặn đạo nhái nghệ sĩ)

# ==============================================================================

def test_gf04_05_rights_and_impersonation_filter(music_fixture):

    """GF04-05: Chặn đứng yêu cầu nhái giọng ca sĩ cụ thể trước khi gửi lệnh sang Provider."""

    adapter = GoogleOfficialLyriaAdapter(api_key="mock-key")



    with pytest.raises(RuntimeError, match="PROMPT_SAFETY_VIOLATION"):

        adapter.generate(

            prompt="Hãy hát bằng giọng ca sĩ Sơn Tùng phong cách Pop",

            workspace_id=music_fixture["ws_id"]

        )





# ==============================================================================

# GF04-06: Prompt Safety Filtering (Provider safety filter block)

# ==============================================================================

def test_gf04_06_prompt_safety_filtering(music_fixture):

    """GF04-06: Provider trả status FAILED do safety filter -> Trả lỗi rõ ràng, không tạo asset giả."""

    def mock_handler(request: httpx.Request):

        body = {

            "status": "FAILED",

            "error": {

                "message": "Content blocked by safety policy (hate_speech/violence)"

            }

        }

        return httpx.Response(200, json=body)



    mock_transport = httpx.MockTransport(mock_handler)

    adapter = GoogleOfficialLyriaAdapter(api_key="mock-key-safety")



    with pytest.raises(RuntimeError, match="PROMPT_SAFETY_VIOLATION"):

        adapter.generate(

            prompt="Prompt bị chặn an toàn",

            workspace_id=music_fixture["ws_id"],

            client_transport=mock_transport

        )





# ==============================================================================

# GF04-07: Flow Pilot Region Blocked / Disabled

# ==============================================================================

def test_gf04_07_flow_pilot_region_or_disabled(music_fixture, monkeypatch):

    """GF04-07: Flow Pilot ở trạng thái DISABLED khi chưa được cấp phép kích hoạt."""

    monkeypatch.delenv("FLOW_MUSIC_PILOT_ENABLED", raising=False)

    adapter = FlowBrowserPilotAdapter()

    assert adapter.is_enabled() is False



    with pytest.raises(RuntimeError, match="PILOT_DISABLED"):

        adapter.generate(

            prompt="Giai điệu guitar",

            workspace_id=music_fixture["ws_id"]

        )





# ==============================================================================

# GF04-08: Instrumental Mode Constraints

# ==============================================================================

def test_gf04_08_instrumental_mode_constraints(music_fixture):

    """GF04-08: Báo giới hạn chỉ hòa tấu khi người dùng yêu cầu lời trên model instrumental."""

    adapter = GoogleOfficialLyriaAdapter(api_key="mock-key")



    with pytest.raises(RuntimeError, match="INSTRUMENTAL_ONLY"):

        adapter.generate(

            prompt="Nhạc hòa tấu",

            lyrics="Lời bài hát không hợp lệ",

            model_id="lyria-instrumental-preview",

            workspace_id=music_fixture["ws_id"]

        )





# ==============================================================================

# GF04-09: True EBU R128 Measurement & Audio QC Pass/Fail

# ==============================================================================

def test_gf04_09_true_ebu_r128_measurement(music_fixture):

    """GF04-09: Đo đạc âm lượng EBU R128 thật và kiểm định QC chính xác."""

    # 1. Tệp âm thanh chuẩn -14 LUFS

    valid_file = music_fixture["tmp_dir"] / "test_valid_lufs.mp3"

    audio_processor.normalize_loudness(

        input_path=music_fixture["music_file"],

        output_path=valid_file,

        target_lufs=-14.0

    )

    qc_valid = audio_processor.verify_audio_qc(valid_file, target_lufs=-14.0, lufs_tolerance=1.5)

    assert qc_valid["passed"] is True

    assert -15.5 <= qc_valid["measured_i_lufs"] <= -12.5



    # 2. Tệp HTML giả mạo -> Bị từ chối ngay lập tức

    fake_html = music_fixture["tmp_dir"] / "fake_error.mp3"

    fake_html.write_text("<!DOCTYPE html><html><body>Error 500 " + ("padding_" * 200) + "</body></html>", encoding="utf-8")

    qc_fake = audio_processor.verify_audio_qc(fake_html)

    assert qc_fake["passed"] is False

    assert "HTML" in qc_fake["reason"]





# ==============================================================================

# GF04-10: Persistent Idempotency & Budget Preflight

# ==============================================================================

def test_gf04_10_persistent_idempotency_and_budget(music_fixture):

    """GF04-10: Persistent Idempotency ràng buộc toàn bộ các trường, và ngân sách chỉ quyết toán khi thành công."""

    idem_key = f"idem-key-{uuid.uuid4().hex[:12]}"

    headers = {

        "Authorization": f"Bearer {music_fixture['token']}",

        "X-Workspace-Id": music_fixture["ws_id"]

    }



    # Request 1: Tạo thành công

    resp1 = client.post(

        "/v1/media/music/generate",

        data={

            "prompt": "Giai điệu Lofi ban đêm",

            "genre": "Lo-Fi",

            "mood": "Calm",

            "idempotency_key": idem_key

        },

        headers=headers

    )

    assert resp1.status_code == 200

    data1 = resp1.json()

    asset_id_1 = data1["id"]



    # Request 2 (Cùng key, cùng toàn bộ payload) -> Phải trả cùng asset_id mà không tạo mới

    resp2 = client.post(

        "/v1/media/music/generate",

        data={

            "prompt": "Giai điệu Lofi ban đêm",

            "genre": "Lo-Fi",

            "mood": "Calm",

            "idempotency_key": idem_key

        },

        headers=headers

    )

    assert resp2.status_code == 200

    data2 = resp2.json()

    assert data2["id"] == asset_id_1



    # Request 3 (Cùng key nhưng đổi lyrics) -> Bắt buộc bị từ chối HTTP 409 IDEMPOTENCY_CONFLICT (Vấn đề 4)

    resp3 = client.post(

        "/v1/media/music/generate",

        data={

            "prompt": "Giai điệu Lofi ban đêm",

            "genre": "Lo-Fi",

            "mood": "Calm",

            "lyrics": "Lời bài hát khác biệt hoàn toàn",

            "idempotency_key": idem_key

        },

        headers=headers

    )

    assert resp3.status_code == 409

    err3 = resp3.json().get("error_code") or (resp3.json().get("detail", {}).get("error_code") if isinstance(resp3.json().get("detail"), dict) else None)

    assert err3 == "IDEMPOTENCY_CONFLICT"



    # Request 4 (Cùng key nhưng đổi duration_sec) -> Bắt buộc bị từ chối HTTP 409 IDEMPOTENCY_CONFLICT (Vấn đề 4)

    resp4 = client.post(

        "/v1/media/music/generate",

        data={

            "prompt": "Giai điệu Lofi ban đêm",

            "genre": "Lo-Fi",

            "mood": "Calm",

            "duration_sec": 45,

            "idempotency_key": idem_key

        },

        headers=headers

    )

    assert resp4.status_code == 409



    # Kiểm tra nguyên tắc Quyết toán ngân sách: Thất bại KHÔNG được phép trừ spent_units (Vấn đề 3)

    with SessionLocal() as db:

        budget = db.query(WorkspaceBudget).filter(WorkspaceBudget.workspace_id == music_fixture["ws_id"]).first()

        spent_before = budget.spent_units if budget else 0.0



    resp_fail = client.post(

        "/v1/media/music/generate",

        data={

            "prompt": "Hãy hát bằng giọng ca sĩ Sơn Tùng phong cách Pop",

            "idempotency_key": f"fail-key-{uuid.uuid4().hex[:12]}"

        },

        headers=headers

    )

    assert resp_fail.status_code in (400, 422)



    with SessionLocal() as db:

        budget = db.query(WorkspaceBudget).filter(WorkspaceBudget.workspace_id == music_fixture["ws_id"]).first()

        spent_after = budget.spent_units if budget else 0.0

        assert spent_after == spent_before, "Tác vụ thất bại không được phép trừ ngân sách"





# ==============================================================================

# GF04-11: Separation of Duties Gate (Rào chắn Bốn Mắt duyệt asset)

# ==============================================================================

def test_gf04_11_separation_of_duties_gate(music_fixture):

    """GF04-11: Asset tạo ra có approval_state = UNREVIEWED; người tạo không được tự duyệt."""

    headers_creator = {

        "Authorization": f"Bearer {music_fixture['token']}",

        "X-Workspace-Id": music_fixture["ws_id"]

    }

    headers_reviewer = {

        "Authorization": f"Bearer {music_fixture['reviewer_token']}",

        "X-Workspace-Id": music_fixture["ws_id"]

    }



    # 1. Tạo bản nhạc

    resp = client.post(

        "/v1/media/music/generate",

        data={

            "prompt": "Bản nhạc hòa tấu piano thư thái",

            "genre": "Classical",

            "mood": "Peaceful"

        },

        headers=headers_creator

    )

    assert resp.status_code == 200

    asset_id = resp.json()["id"]



    # Kiểm tra trong DB: Trạng thái ban đầu bắt buộc là UNREVIEWED

    with SessionLocal() as db:

        asset = db.query(MediaAsset).filter(MediaAsset.id == asset_id).first()

        assert asset.approval_state == "UNREVIEWED"



    # 2. Người tạo (Creator) tự gọi duyệt APPROVE -> Bị từ chối HTTP 403 Forbidden

    resp_self = client.post(

        f"/v1/media/assets/{asset_id}/review",

        data={"decision": "APPROVE"},

        headers=headers_creator

    )

    assert resp_self.status_code == 403

    err_self = resp_self.json().get("error_code") or (resp_self.json().get("detail", {}).get("error_code") if isinstance(resp_self.json().get("detail"), dict) else None)

    assert err_self == "SEPARATION_OF_DUTIES_VIOLATION"



    # 3. Người kiểm duyệt độc lập (Reviewer) duyệt APPROVE -> Thành công HTTP 200

    resp_rev = client.post(

        f"/v1/media/assets/{asset_id}/review",

        data={"decision": "APPROVE", "review_notes": "Đạt chuẩn âm lượng TikTok"},

        headers=headers_reviewer

    )

    assert resp_rev.status_code == 200

    assert resp_rev.json()["approval_state"] == "APPROVED"





# ==============================================================================

# GF04-12: Session Revocation Fail-Closed (FLOW_LOGIN_REQUIRED)

# ==============================================================================

def test_gf04_12_session_revocation_fail_closed(music_fixture, monkeypatch):

    """GF04-12: Thiếu phiên Flow đăng nhập -> Trả mã lỗi FLOW_LOGIN_REQUIRED (401)."""

    import src.modules.media_studio.router as router_module

    from session_manager import FlowLoginRequired



    def fail_flow(**kwargs):

        raise FlowLoginRequired("Chưa đăng nhập Google Flow")



    monkeypatch.setattr(router_module.music_orchestrator, "generate_music_track", fail_flow)



    resp = client.post(

        "/v1/media/music/generate",

        data={"prompt": "Nhạc nền Flow", "provider": "FLOW_BROWSER_PILOT"},

        headers={

            "Authorization": f"Bearer {music_fixture['token']}",

            "X-Workspace-Id": music_fixture["ws_id"]

        }

    )

    assert resp.status_code == 401

    err_code = resp.json().get("error_code") or (resp.json().get("detail", {}).get("error_code") if isinstance(resp.json().get("detail"), dict) else None)

    assert err_code == "FLOW_LOGIN_REQUIRED"





# ==============================================================================

# GF04-13: Capabilities Endpoint Probe

# ==============================================================================

def test_gf04_13_capabilities_endpoint(music_fixture):

    """GF04-13: Endpoint GET /v1/media/music/capabilities trả về danh sách năng lực trung thực."""

    resp = client.get(

        "/v1/media/music/capabilities",

        headers={

            "Authorization": f"Bearer {music_fixture['token']}",

            "X-Workspace-Id": music_fixture["ws_id"]

        }

    )

    assert resp.status_code == 200

    data = resp.json()

    assert "items" in data

    assert len(data["items"]) >= 3

    # Xác nhận các provider chuẩn

    providers = [i["provider"] for i in data["items"]]

    assert "GOOGLE_OFFICIAL" in providers

    assert "FLOW_BROWSER_PILOT" in providers

    assert "LOCAL_TEST_SYNTH" in providers


def test_music_job_status_recovers_saved_real_asset(music_fixture):
    """Giao diện có thể lấy asset thật từ job dù phản hồi tạo ban đầu bị mất."""
    key = f"recover-{uuid.uuid4().hex[:12]}"
    asset_id = f"asset-{uuid.uuid4().hex[:12]}"
    with SessionLocal() as db:
        db.add(MediaAsset(
            id=asset_id,
            workspace_id=music_fixture["ws_id"],
            storage_key=f"workspaces/{music_fixture['ws_id']}/media/real.mp3",
            sha256="a" * 64,
            byte_size=50000,
            mime_detected="audio/mpeg",
            source_product="FLOW_MUSIC_PILOT",
            original_filename="real.mp3",
            approval_state="UNREVIEWED",
            created_by=music_fixture["user_id"],
        ))
        db.add(AIGenerationJob(
            id=str(uuid.uuid4()),
            workspace_id=music_fixture["ws_id"],
            asset_type="MUSIC",
            provider="FLOW_BROWSER_PILOT",
            provider_mode="PILOT_ASSISTED",
            model_id="flow-music-web",
            idempotency_key=key,
            state="SUCCEEDED",
            credits_source="FLOW_MUSIC_PLUS",
            request_payload_json="{}",
            output_asset_ids_json=json.dumps([asset_id]),
            created_by=music_fixture["user_id"],
        ))
        db.commit()

    response = client.get(
        f"/v1/media/music/jobs/{key}",
        headers={"Authorization": f"Bearer {music_fixture['token']}", "X-Workspace-Id": music_fixture["ws_id"]},
    )
    assert response.status_code == 200
    assert response.json()["state"] == "SUCCEEDED"
    assert response.json()["provider"] == "FLOW_BROWSER_PILOT"
    assert response.json()["model_id"] == "flow-music-web"
    assert response.json()["credits_source"] == "FLOW_MUSIC_PLUS"
    assert response.json()["asset"]["id"] == asset_id
    assert response.json()["asset"]["url"].endswith("download?ttl=3600")

