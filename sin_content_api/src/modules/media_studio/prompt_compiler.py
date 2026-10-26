# -*- coding: utf-8 -*-
"""Biên dịch brief người dùng thành chỉ thị video rõ ràng, nhất quán."""

from typing import List

from pydantic import BaseModel


class CompiledVideoPrompt(BaseModel):
    raw_prompt: str
    compiled_directive: str
    shot_type: str
    camera_movement: str
    lighting_atmosphere: str
    kinetic_action: str
    retention_hook_3s: str
    suggested_audio_sfx: str
    aspect_ratio: str = "16:9"
    target_duration_seconds: int = 10
    model_target: str = "Omni 1.1 Flash"
    creator_guidelines: List[str]


class VideoPromptCompiler:
    """Mở rộng brief mà không tự thêm nội dung cảnh không được yêu cầu."""

    def compile(
        self,
        user_prompt: str,
        aspect_ratio: str = "16:9",
        duration_seconds: int = 10,
        style: str = "cinematic",
        language: str = "vi",
    ) -> CompiledVideoPrompt:
        clean = user_prompt.strip()
        shot_type = "Bố cục làm rõ chủ thể và bối cảnh đã nêu trong brief"
        camera_movement = "Máy quay ổn định, chuyển động tự nhiên; giữ nguyên chỉ dẫn góc máy của brief"
        lighting = "Ánh sáng và màu sắc phù hợp thời điểm, địa điểm và phong cách đã nêu"
        kinetic_action = "Thể hiện đúng hành động trong brief với diễn tiến tự nhiên, liên tục và nhất quán"
        retention_hook = "Trong 3 giây đầu, làm rõ chủ thể và hành động chính đã được yêu cầu"
        sfx = "Âm thanh môi trường phù hợp với bối cảnh; không thêm lời thoại nếu brief không yêu cầu"

        if language == "en":
            compiled_directive = (
                f"Create a {aspect_ratio} video, {duration_seconds} seconds long, in {style} style. "
                f"Authoritative visual brief: {clean} "
                "Preserve the specified subject, action, setting, time, camera, colors, and exclusions. "
                "Do not invent characters, props, text, logos, actions, or story details. "
                "Create one continuous shot with a clear beginning, development, and natural ending; cut only when requested. "
                "Keep shapes, clothing, objects, direction of travel, and lighting consistent. Use physically plausible, smooth motion and one simple, steady camera move. "
                "Keep focus and subject sharp; no focus breathing, blur, distortion, duplicated objects, flicker, or unrequested text. "
                + ("Compose natively in vertical 9:16; keep the subject and action in the central safe area, with no blurred background or borders."
                   if aspect_ratio == "9:16" else
                   "Compose natively in horizontal widescreen 16:9; keep the subject and action inside the frame, with no blurred background or borders."
                   if aspect_ratio == "16:9" else "")
            )
        else:
            compiled_directive = (
                f"Tạo video {aspect_ratio}, thời lượng {duration_seconds} giây, phong cách {style}. "
                f"Brief gốc của người dùng: {clean} "
                "Xem brief là nguồn chân lý: giữ nguyên chủ thể, hành động, bối cảnh, thời điểm, "
                "góc máy, màu sắc và các điều kiện phủ định được nêu; không tự thêm nhân vật, "
                "đạo cụ, chữ, logo, hành động hoặc chi tiết cốt truyện. "
                "Dàn dựng một cảnh liền mạch, có mở đầu, diễn tiến và kết thúc tự nhiên; "
                "chỉ cắt cảnh khi brief yêu cầu. Duy trì hình dạng, trang phục, vật thể và hướng chuyển động "
                "nhất quán qua toàn bộ video. Dùng chuyển động máy quay ổn định và ánh sáng phù hợp brief; "
                "ưu tiên hình ảnh chân thực, chuyển động tự nhiên, không méo hình, không nhân đôi vật thể, "
                "không nhấp nháy hoặc chèn chữ ngoài yêu cầu. "
                "Giữ tiêu cự và độ nét ổn định, không thở nét, không làm mờ chủ thể. "
                "Chỉ một chuyển động camera đơn giản, tốc độ đều; không tăng tốc, giật lùi hoặc đổi hướng đột ngột. "
                + ("Bố cục dọc gốc 9:16, đặt chủ thể và hành động trong vùng trung tâm an toàn, không tạo viền hoặc nền mờ."
                   if aspect_ratio == "9:16" else "")
            )
        guidelines = [
            f"Khung hình đầu ra: {aspect_ratio}, thời lượng {duration_seconds} giây.",
            "Brief gốc được giữ nguyên làm căn cứ; các chi tiết không có trong brief không được tự suy diễn.",
            f"Mở đầu 3 giây: {retention_hook}.",
            f"Âm thanh gợi ý: {sfx}.",
        ]

        return CompiledVideoPrompt(
            raw_prompt=clean,
            compiled_directive=compiled_directive,
            shot_type=shot_type,
            camera_movement=camera_movement,
            lighting_atmosphere=lighting,
            kinetic_action=kinetic_action,
            retention_hook_3s=retention_hook,
            suggested_audio_sfx=sfx,
            aspect_ratio=aspect_ratio,
            target_duration_seconds=duration_seconds,
            creator_guidelines=guidelines,
        )


video_prompt_compiler = VideoPromptCompiler()
