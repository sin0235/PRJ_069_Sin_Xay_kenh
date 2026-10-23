from typing import List, Dict, Any, Tuple, Optional

class TimingCalculator:
    """
    Kiem soat thoi luong phan canh (Timing & Tolerance Control):
    - Tinh toan thoi diem bat dau (start_seconds) va ket thuc (end_seconds) lien tuc, khong chong cheo.
    - Kiem tra tong thoi luong co nam trong dung sai cho phep (+/- 3 giay) cua target duration.
    - Kiem tra so luong bien the Hook co dat toi thieu >= 2 bien the.
    """

    def __init__(self, default_tolerance_seconds: int = 3):
        self.default_tolerance_seconds = default_tolerance_seconds

    def validate_and_calculate_timing(
        self,
        target_duration_seconds: int,
        blocks: List[Dict[str, Any]],
        hook_variants: List[str],
        tolerance_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        tolerance = tolerance_seconds if tolerance_seconds is not None else self.default_tolerance_seconds

        current_time = 0
        timed_blocks = []
        has_overlap = False

        for idx, block in enumerate(blocks):
            duration = int(block.get("duration_seconds", 5))
            start_sec = current_time
            end_sec = current_time + duration
            current_time = end_sec

            timed_blocks.append({
                "block_type": block.get("block_type", "VALUE"),
                "narration": block.get("narration", ""),
                "visual_cue": block.get("visual_cue", ""),
                "duration_seconds": duration,
                "start_seconds": start_sec,
                "end_seconds": end_sec
            })

        actual_duration = current_time
        duration_diff = abs(actual_duration - target_duration_seconds)
        tolerance_passed = duration_diff <= tolerance

        # Kiem tra bien the Hook
        hook_variants_count = len(hook_variants)
        hook_variants_valid = hook_variants_count >= 2

        return {
            "actual_duration_seconds": actual_duration,
            "target_duration_seconds": target_duration_seconds,
            "tolerance_seconds": tolerance,
            "duration_diff": duration_diff,
            "duration_tolerance_passed": tolerance_passed,
            "has_overlap": has_overlap,
            "hook_variants_count": hook_variants_count,
            "hook_variants_valid": hook_variants_valid,
            "timed_blocks": timed_blocks
        }

timing_calculator = TimingCalculator()
