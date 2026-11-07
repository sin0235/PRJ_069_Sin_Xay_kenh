from src.modules.media_studio.prompt_compiler import VideoPromptCompiler


def test_compiler_expands_user_brief_without_inventing_scene_details():
    brief = "Một chiếc xe đạp đỏ chạy chậm qua con phố mưa lúc bình minh, góc rộng, không có người."

    result = VideoPromptCompiler().compile(brief)

    assert brief in result.compiled_directive
    assert "không có người" in result.compiled_directive
    assert "ly cà phê" not in result.compiled_directive
    assert "Retention Rate > 70%" not in result.compiled_directive


def test_compiler_uses_requested_duration_and_aspect_ratio_in_directive():
    result = VideoPromptCompiler().compile(
        "Một chiếc xe đạp đỏ chạy chậm qua con phố mưa lúc bình minh.",
        aspect_ratio="9:16",
        duration_seconds=7,
    )

    assert result.target_duration_seconds == 7
    assert "B\u1ed1 c\u1ee5c d\u1ecdc g\u1ed1c 9:16" in result.compiled_directive
    assert "kh\u00f4ng l\u00e0m m\u1edd ch\u1ee7 th\u1ec3" in result.compiled_directive
    assert "9:16" in result.compiled_directive
    assert "7 giây" in result.compiled_directive
    assert "10 giây" not in result.compiled_directive


def test_compiler_uses_english_instructions_for_english_flow_prompts():
    result = VideoPromptCompiler().compile(
        "A paper assistant folds one corner inward, then holds the pose.",
        aspect_ratio="9:16",
        language="en",
    )

    assert "Authoritative visual brief" in result.compiled_directive
    assert "Compose natively in vertical 9:16" in result.compiled_directive
    assert "Bố cục" not in result.compiled_directive


def test_compiler_allows_connected_multiphase_camera_moves():
    brief = "Máy quay hạ thấp, dolly tiến rồi orbit quanh chủ thể trong một cú máy liên tục."
    result = VideoPromptCompiler().compile(brief)

    assert brief in result.compiled_directive
    assert "tối đa ba pha liên kết" in result.compiled_directive
    assert "Chỉ một chuyển động camera đơn giản" not in result.compiled_directive


def test_english_flow_prompt_allows_connected_multiphase_camera_moves():
    brief = "Crane down, dolly in, then orbit around the subject in one continuous shot."
    result = VideoPromptCompiler().compile(brief, language="en")

    assert brief in result.compiled_directive
    assert "up to three connected phases" in result.compiled_directive
    assert "one simple, steady camera move" not in result.compiled_directive
