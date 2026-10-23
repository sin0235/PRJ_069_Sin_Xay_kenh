# Ranking Service (P07 / T070, T071, T072, T073, P07-01, P07-02, P07-07)
# Ket noi ExplicitScorer, HybridSearchEngine va Danh gia Tap Du Lieu Vang (Precision@10 >= 80%).

import os
import re
import json
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException
from src.models.entities import BrandBriefVersion
from src.schemas.contracts import (
    CandidateScoreRequest,
    HybridSearchRequest,
    ScoringBreakdown
)
from src.modules.retrieval.scorer import ExplicitScorer
from src.modules.retrieval.hybrid_search import HybridSearchEngine

# Tinh toan duong dan tap du lieu vang
API_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
GOLD_SETS_DIR = os.path.join(API_ROOT, "evals", "gold_sets")
if not os.path.exists(GOLD_SETS_DIR):
    GOLD_SETS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "evals", "gold_sets"))

class RankingService:
    @staticmethod
    def get_scoring_weights() -> Dict[str, float]:
        """Lay ma tran trong so cham diem tuong minh (T070)."""
        return ExplicitScorer.get_weights()

    @staticmethod
    def _extract_brief_lists(brief: BrandBriefVersion):
        """Lay an toan cac danh sach topics va limits tu brief."""
        if hasattr(brief, "topics_included") and isinstance(brief.topics_included, list):
            topics_inc = brief.topics_included
        else:
            topics_inc = json.loads(getattr(brief, "topics_included_json", "[]") or "[]")

        if hasattr(brief, "topics_excluded") and isinstance(brief.topics_excluded, list):
            topics_exc = brief.topics_excluded
        else:
            topics_exc = json.loads(getattr(brief, "topics_excluded_json", "[]") or "[]")

        if hasattr(brief, "production_limits") and isinstance(brief.production_limits, list):
            limits = brief.production_limits
        else:
            limits = json.loads(getattr(brief, "production_limits_json", "[]") or "[]")

        return topics_inc, topics_exc, limits

    @classmethod
    def score_candidate(
        cls,
        db: Session,
        workspace_id: str,
        data: CandidateScoreRequest
    ) -> Dict[str, Any]:
        """Cham diem tuong minh cho 1 ung vien so voi brief (T070, T071, T073, P07-07)."""
        brief = db.query(BrandBriefVersion).filter(
            BrandBriefVersion.id == data.brief_version_id,
            BrandBriefVersion.workspace_id == workspace_id
        ).first()

        if not brief:
            raise ValueError(f"BriefVersion {data.brief_version_id} không tồn tại trong workspace {workspace_id}")

        # P07-07: Bat buoc brief phai o trang thai APPROVED
        if getattr(brief, "status", None) != "APPROVED":
            raise HTTPException(
                status_code=422,
                detail=f"BriefVersion {data.brief_version_id} chưa được phê duyệt (status != APPROVED). Không thể chấm điểm."
            )

        topics_inc, topics_exc, limits = cls._extract_brief_lists(brief)

        score_res = ExplicitScorer.score_candidate(
            candidate_title=data.candidate_title,
            content_excerpt=data.content_excerpt,
            topics_included=topics_inc,
            topics_excluded=topics_exc,
            objective=brief.objective,
            target_audience=brief.target_audience,
            production_limits=limits,
            evidence_tier=data.evidence_tier,
            observed_vs_inferred=data.observed_vs_inferred,
            snapshots=data.snapshots
        )

        return {
            "candidate_id": data.candidate_id,
            "breakdown": ScoringBreakdown(**score_res),
            "status": score_res["status"]
        }

    @classmethod
    def search_hybrid(
        cls,
        db: Session,
        workspace_id: str,
        data: HybridSearchRequest
    ) -> Dict[str, Any]:
        """Tim kiem lai va xep hang ung vien trong workspace (P07-07)."""
        brief = db.query(BrandBriefVersion).filter(
            BrandBriefVersion.id == data.brief_version_id,
            BrandBriefVersion.workspace_id == workspace_id
        ).first()

        if not brief:
            raise ValueError(f"BriefVersion {data.brief_version_id} không tồn tại trong workspace {workspace_id}")

        # P07-07: Bat buoc brief phai o trang thai APPROVED
        if getattr(brief, "status", None) != "APPROVED":
            raise HTTPException(
                status_code=422,
                detail=f"BriefVersion {data.brief_version_id} chưa được phê duyệt (status != APPROVED). Không thể tìm kiếm xếp hạng."
            )

        results = HybridSearchEngine.search(
            db=db,
            workspace_id=workspace_id,
            brief=brief,
            query=data.query,
            intent_group=data.intent_group,
            need_category=data.need_category,
            limit=data.limit,
            provider_ids=data.provider_ids
        )

        return {
            "total_found": len(results),
            "results": results
        }

    @classmethod
    def evaluate_gold_dataset(
        cls,
        dataset_name: str = "bento_box_gold.json"
    ) -> Dict[str, Any]:
        """
        Danh gia do chinh xac Top 10 (Precision@10) tren tap du lieu vang (T072).
        Tieu chuan cong bat buoc: Precision@10 >= 80% (it nhat 8/10 ung vien duyet la RELEVANT).
        0 ung vien vi pham Veto duoc phep lot vao Top 10.
        P07-02: Path traversal protection.
        P07-01: Cham diem trung thuc, khong cheat bang adjudication_label.
        """
        # P07-02: Validate dataset_name khong duoc chua duong dan tuong doi hoac ky tu la
        clean_name = os.path.basename(dataset_name)
        if not re.match(r"^[a-zA-Z0-9_\-\.]+\.json$", clean_name) or clean_name != dataset_name:
            raise ValueError(f"Tên dataset không hợp lệ: {dataset_name}")

        filepath = os.path.abspath(os.path.join(GOLD_SETS_DIR, clean_name))
        gold_sets_abs = os.path.abspath(GOLD_SETS_DIR)
        if not filepath.startswith(gold_sets_abs) or not os.path.exists(filepath):
            raise FileNotFoundError(f"Không tìm thấy tập dữ liệu vàng tại {dataset_name}")

        with open(filepath, "r", encoding="utf-8") as f:
            candidates = json.load(f)

        brief_id = candidates[0].get("brief_id", "brief-gold")
        brief_name = candidates[0].get("brief_name", "Gold Brief")

        # Thiet lap cac tham so brief phu hop cho tung tap du lieu vang
        if "skincare" in dataset_name.lower():
            topics_included = ["serum phục hồi", "dưỡng ẩm da", "lành tính", "an toàn", "chăm sóc da"]
            topics_excluded = ["kem trộn", "chất tẩy trắng", "lừa đảo", "hàng giả"]
            objective = "Phát triển nội dung TikTok chứng minh hiệu quả cấp ẩm và phục hồi da dịu nhẹ"
            target_audience = "Phụ nữ trẻ, nhân viên văn phòng, người có làn da nhạy cảm"
            production_limits = ["quay video cận cảnh"]
        elif "audio" in dataset_name.lower():
            topics_included = ["tai nghe chống ồn", "đàm thoại rõ", "cách âm tốt", "pin trâu", "tiện lợi"]
            topics_excluded = ["hàng nhái", "cháy nổ pin", "lừa đảo", "kém chất lượng"]
            objective = "Phát triển nội dung TikTok chứng minh khả năng chống ồn chủ động ANC và chất lượng đàm thoại"
            target_audience = "Người làm việc từ xa, sinh viên, người di chuyển nhiều trên máy bay/xe bus"
            production_limits = ["thử thách độ trễ"]
        else: # bento
            topics_included = ["hộp cơm giữ nhiệt", "chống tràn canh", "inox 304", "an toàn sức khỏe", "tiện lợi"]
            topics_excluded = ["cháy nổ", "lừa đảo", "hàng giả", "chất độc hại"]
            objective = "Phát triển nội dung TikTok chứng minh khả năng chống tràn và giữ nhiệt của hộp cơm văn phòng"
            target_audience = "Dân văn phòng, người đi xe máy, sinh viên"
            production_limits = ["thời lượng dưới 60s"]

        scored_list = []
        for c in candidates:
            # P07-01: Khong truyen adjudication_label hay has_veto_violation vao scorer de cheat!
            score_data = ExplicitScorer.score_candidate(
                candidate_title=c.get("candidate_title", ""),
                content_excerpt=c.get("content_excerpt", ""),
                topics_included=topics_included,
                topics_excluded=topics_excluded,
                objective=objective,
                target_audience=target_audience,
                production_limits=production_limits,
                evidence_tier=c.get("evidence_tier", "LIMITED_SIGNAL"),
                observed_vs_inferred="OBSERVED_DIRECT",
                adjudication_label=None,
                has_veto_violation=False
            )

            scored_list.append({
                "candidate": c,
                "score_data": score_data,
                "overall_score": score_data["overall_score"]
            })

        # Sap xep giam dan theo overall_score
        scored_list.sort(key=lambda item: item["overall_score"], reverse=True)

        # Lay Top 10
        top_10 = scored_list[:10]
        relevant_count = sum(1 for item in top_10 if item["candidate"].get("adjudication_label") == "RELEVANT")
        veto_count = sum(1 for item in top_10 if item["candidate"].get("has_veto_violation") or item["score_data"].get("veto_violation"))
        precision = round(float(relevant_count) / 10.0, 4)

        meets_threshold = precision >= 0.80 and veto_count == 0

        return {
            "brief_id": brief_id,
            "brief_name": brief_name,
            "total_candidates": len(candidates),
            "top_10_precision": precision,
            "top_10_relevant_count": relevant_count,
            "top_10_veto_count": veto_count,
            "meets_threshold": meets_threshold,
            "top_10_candidates": [
                {
                    "id": item["candidate"].get("id"),
                    "title": item["candidate"].get("candidate_title"),
                    "overall_score": item["overall_score"],
                    "adjudication_label": item["candidate"].get("adjudication_label"),
                    "has_veto_violation": item["candidate"].get("has_veto_violation")
                }
                for item in top_10
            ]
        }

ranking_service = RankingService()
