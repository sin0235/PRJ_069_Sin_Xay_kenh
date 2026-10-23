# Explicit Scoring Engine (P07 / T070, T071, T073, P07-01, P07-05, P07-06, P07-09, P07-11)
# Thuat toan cham diem tuong minh theo trong so co dinh:
# 1. Phu hop khan gia (Audience Fit): 30% (0.30)
# 2. Bang chung quan sat (Observed Evidence): 25% (0.25)
# 3. Muc tieu thuong hieu (Brand Objective): 20% (0.20)
# 4. Tinh doc dao (Content Uniqueness / Novelty): 15% (0.15)
# 5. Tinh kha thi san xuat (Production Feasibility): 10% (0.10)
# Tong trong so: Dung 100% (1.00).

import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

# Trong so tuong minh co dinh
WEIGHTS = {
    "audience_fit": 0.30,
    "observed_evidence": 0.25,
    "brand_objective": 0.20,
    "content_uniqueness": 0.15,
    "production_feasibility": 0.10
}

assert sum(WEIGHTS.values()) == 1.00, "Tổng trọng số bắt buộc phải bằng đúng 1.00 (100%)"

class ExplicitScorer:
    @staticmethod
    def get_weights() -> Dict[str, float]:
        """Tra ve ma tran trong so tuong minh co dinh."""
        return {**WEIGHTS, "total": sum(WEIGHTS.values())}

    @classmethod
    def check_veto_violation(
        cls,
        text: str,
        topics_excluded: List[str]
    ) -> Tuple[bool, Optional[str]]:
        """
        Kiem tra vi pham quy tac phu quyet (Brand Safety Veto - T071).
        Neu noi dung chua chu de bi cam, bi phu quyet ngay lap tuc.
        """
        if not text or not topics_excluded:
            return False, None

        text_lower = text.lower()
        for term in topics_excluded:
            t = term.strip().lower()
            if not t:
                continue
            pattern = rf"\b{re.escape(t)}\b"
            if re.search(pattern, text_lower) or t in text_lower:
                return True, f"Nội dung chứa chủ đề bị cấm (topics_excluded): '{term}'"

        return False, None

    @classmethod
    def calculate_growth_velocity(
        cls,
        snapshots: Optional[List[Dict[str, Any]]]
    ) -> Tuple[Optional[float], str, str]:
        """
        Kiem tra snapshot chi so (T073, P07-06):
        Chi co 1 snapshot -> NOT_AVAILABLE, UNVERIFIED_SINGLE_SNAPSHOT, khong suy dien tang truong.
        Co >= 2 snapshots -> Kiem tra thoi gian hop le (t2 > t1) -> Tinh velocity = delta_views / delta_days.
        Khong co observed_at hoac t2 <= t1 -> NOT_AVAILABLE, INVALID_SNAPSHOT_TIMESTAMPS.
        """
        if not snapshots or len(snapshots) < 2:
            return None, "NOT_AVAILABLE", "UNVERIFIED_SINGLE_SNAPSHOT"

        # P07-06: Kiem tra snapshot hop le truoc khi tinh
        parsed_snaps = []
        for s in snapshots:
            t = s.get("observed_at")
            v = s.get("view_count")
            if v is None:
                continue
            if isinstance(t, str):
                try:
                    t_parsed = datetime.fromisoformat(t.replace("Z", "+00:00"))
                except Exception:
                    t_parsed = None
            elif isinstance(t, datetime):
                t_parsed = t
            else:
                t_parsed = None

            if t_parsed is None:
                # P07-06: Thieu observed_at hop le -> khong the tinh velocity
                return None, "NOT_AVAILABLE", "INVALID_SNAPSHOT_TIMESTAMPS"
            parsed_snaps.append((t_parsed, float(v)))

        if len(parsed_snaps) < 2:
            return None, "NOT_AVAILABLE", "UNVERIFIED_SINGLE_SNAPSHOT"

        parsed_snaps.sort(key=lambda item: item[0])
        t1, v1 = parsed_snaps[0]
        t2, v2 = parsed_snaps[-1]

        delta_seconds = (t2 - t1).total_seconds()
        if delta_seconds <= 0:
            # P07-06: Snapshots cung thoi gian hoac chuoi thoi gian sai
            return None, "NOT_AVAILABLE", "INVALID_SNAPSHOT_TIMESTAMPS"

        delta_days = delta_seconds / 86400.0
        velocity = round(float(v2 - v1) / delta_days, 2)
        return velocity, "CALCULATED", "VERIFIED_MULTI_SNAPSHOT"

    @classmethod
    def score_candidate(
        cls,
        candidate_title: str,
        content_excerpt: str,
        topics_included: List[str],
        topics_excluded: List[str],
        objective: str,
        target_audience: str,
        production_limits: List[str],
        evidence_tier: str = "LIMITED_SIGNAL",
        observed_vs_inferred: str = "OBSERVED_DIRECT",
        snapshots: Optional[List[Dict[str, Any]]] = None,
        adjudication_label: Optional[str] = None,
        has_veto_violation: bool = False
    ) -> Dict[str, Any]:
        """
        Cham diem tuong minh tat dinh (deterministic) tren 5 thanh phan.
        P07-01: Loai bo hoan toan cheat adjudication_label, cham diem trung thuc dua tren noi dung.
        P07-11: Cung cap component_reasons ro rang cho nguoi dung/reviewer.
        """
        combined_text = f"{candidate_title} {content_excerpt}".strip()
        reasons = {}

        # 1. Kiem tra VETO vi pham (T071)
        is_veto, veto_reason = cls.check_veto_violation(combined_text, topics_excluded)
        if has_veto_violation or is_veto:
            reason = veto_reason or "Phát hiện vi phạm quy tắc phủ quyết (Veto Rule)"
            v_val, v_stat, v_conf = cls.calculate_growth_velocity(snapshots)
            return {
                "audience_fit_score": 0.0,
                "observed_evidence_score": 0.0,
                "brand_objective_score": 0.0,
                "content_uniqueness_score": 0.0,
                "production_feasibility_score": 0.0,
                "overall_score": 0.0,
                "veto_violation": True,
                "veto_reason": reason,
                "growth_velocity": v_val,
                "velocity_status": v_stat,
                "velocity_confidence": v_conf,
                "component_reasons": {"veto": reason},
                "status": "REJECTED_VETO"
            }

        # 2. Audience Fit (30%): Khop khan gia muc tieu va nhu cau
        aud_lower = target_audience.lower() if target_audience else ""
        text_lower = combined_text.lower()

        aud_keywords = [w.strip() for w in re.split(r"[,;/\s]+", aud_lower) if len(w.strip()) > 3]
        matches_aud = sum(1 for kw in aud_keywords if kw in text_lower)
        if matches_aud >= 2:
            s_audience = 9.0
            reasons["audience_fit"] = f"Khớp nhiều nhóm từ khóa khán giả mục tiêu ({matches_aud} từ khóa)"
        elif matches_aud == 1:
            s_audience = 7.5
            reasons["audience_fit"] = "Khớp 1 từ khóa khán giả mục tiêu"
        elif any(term in text_lower for term in ["văn phòng", "học sinh", "sinh viên", "gia đình", "người dùng", "phụ nữ", "làm việc"]):
            s_audience = 7.0
            reasons["audience_fit"] = "Khớp từ khóa đối tượng phổ thông phù hợp"
        else:
            s_audience = 4.0
            reasons["audience_fit"] = "Chưa tìm thấy từ khóa đặc trưng của khán giả mục tiêu"

        # 3. Observed Evidence (25%): Do vung chac cua bang chung quan sat (P07-05)
        if evidence_tier == "EVIDENCE_BACKED" and observed_vs_inferred == "OBSERVED_DIRECT":
            s_evidence = 9.5
            reasons["observed_evidence"] = "Bằng chứng quan sát trực tiếp vững chắc (EVIDENCE_BACKED)"
        elif evidence_tier == "EVIDENCE_BACKED":
            s_evidence = 8.0
            reasons["observed_evidence"] = "Bằng chứng quan sát có suy luận bổ trợ"
        elif evidence_tier == "LIMITED_SIGNAL" and observed_vs_inferred == "OBSERVED_DIRECT":
            s_evidence = 6.5
            reasons["observed_evidence"] = "Tín hiệu quan sát trực tiếp nhưng giới hạn mẫu"
        elif evidence_tier == "LIMITED_SIGNAL":
            s_evidence = 5.0
            reasons["observed_evidence"] = "Tín hiệu thị trường hạn chế (LIMITED_SIGNAL)"
        else: # HYPOTHESIS hoac INFERRED_UNVERIFIED
            s_evidence = 2.5
            reasons["observed_evidence"] = "Giả thuyết hoặc suy luận chưa qua kiểm chứng (INFERRED_UNVERIFIED)"

        # 4. Brand Objective (20%): Khop muc tieu va topics_included
        obj_matches = sum(1 for inc in topics_included if inc.lower() in text_lower)
        if obj_matches >= 2:
            s_brand = 9.0
            reasons["brand_objective"] = f"Khớp {obj_matches} chủ đề mục tiêu trọng tâm của thương hiệu"
        elif obj_matches == 1:
            s_brand = 7.5
            reasons["brand_objective"] = "Khớp 1 chủ đề mục tiêu của thương hiệu"
        elif any(w in text_lower for w in ["chất lượng", "an toàn", "tiện lợi", "giải pháp", "hiệu quả"]):
            s_brand = 6.5
            reasons["brand_objective"] = "Khớp các giá trị công năng cơ bản của mục tiêu"
        else:
            s_brand = 3.5
            reasons["brand_objective"] = "Chưa thể hiện rõ các chủ đề mục tiêu của thương hiệu"

        # 5. Content Uniqueness / Novelty (15%): Tinh doc dao, hook loi cuon
        if any(term in text_lower for term in ["thử thách", "so sánh", "kiểm tra", "review chi tiết", "góc khuất"]):
            s_novelty = 8.5
            reasons["content_uniqueness"] = "Định dạng thử nghiệm/so sánh có tính tương tác cao"
        elif any(term in text_lower for term in ["mẹo", "hướng dẫn", "bật mí", "trải nghiệm"]):
            s_novelty = 7.5
            reasons["content_uniqueness"] = "Nội dung chia sẻ kinh nghiệm hữu ích"
        else:
            s_novelty = 5.5
            reasons["content_uniqueness"] = "Nội dung phản ánh sự việc thông thường"

        # 6. Production Feasibility (10%): Tinh kha thi san xuat (P07-09)
        # Khong tru diem neu trich dan dung dieu kien; chi tru diem neu co vi pham ro ret
        s_feasibility = 8.0
        reasons["production_feasibility"] = "Phù hợp năng lực sản xuất nội dung ngắn tiêu chuẩn"
        if production_limits:
            violation_terms = ["chi phí tiền tỷ", "thuê trường quay chuyên nghiệp", "quay flycam đắt đỏ", "thời lượng trên 3 phút"]
            for v_term in violation_terms:
                if v_term in text_lower:
                    s_feasibility = 3.0
                    reasons["production_feasibility"] = f"Vi phạm giới hạn sản xuất: {v_term}"
                    break

        # Tinh toan Velocity & Snapshot check (T073, P07-06)
        v_val, v_stat, v_conf = cls.calculate_growth_velocity(snapshots)

        # 7. Tinh tong diem tat dinh theo dung trong so (T070)
        overall = (
            s_audience * WEIGHTS["audience_fit"] +
            s_evidence * WEIGHTS["observed_evidence"] +
            s_brand * WEIGHTS["brand_objective"] +
            s_novelty * WEIGHTS["content_uniqueness"] +
            s_feasibility * WEIGHTS["production_feasibility"]
        )
        overall_score = round(overall, 4)

        return {
            "audience_fit_score": round(s_audience, 2),
            "observed_evidence_score": round(s_evidence, 2),
            "brand_objective_score": round(s_brand, 2),
            "content_uniqueness_score": round(s_novelty, 2),
            "production_feasibility_score": round(s_feasibility, 2),
            "overall_score": overall_score,
            "veto_violation": False,
            "veto_reason": None,
            "growth_velocity": v_val,
            "velocity_status": v_stat,
            "velocity_confidence": v_conf,
            "component_reasons": reasons,
            "status": "APPROVED_RANKED" if overall_score >= 6.0 else "LOW_SCORE"
        }
