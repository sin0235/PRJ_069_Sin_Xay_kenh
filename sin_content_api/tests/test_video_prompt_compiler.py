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
    assert "9:16" in result.compiled_directive
    assert "7 giây" in result.compiled_directive
    assert "10 giây" not in result.compiled_directive
