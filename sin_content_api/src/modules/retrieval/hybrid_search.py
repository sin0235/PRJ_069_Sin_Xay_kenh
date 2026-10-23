# Hybrid Search Engine (P07 / T071, P07-03, P07-04, P07-05, P07-08, P07-10)
# Ket hop 3 tang: Bo loc cau truc (Structured Filter) + Full-text Matching + Semantic Cosine Similarity.
# Bo loc bat buoc loai bo chu de cam (topics_excluded) khong the bi qua mat boi view cao.

import re
import math
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from src.models.entities import SourceRecord, EvidenceExcerpt, MetricSnapshot, BrandBriefVersion, NeedSignal
from src.modules.retrieval.scorer import ExplicitScorer

class HybridSearchEngine:
    @staticmethod
    def compute_text_similarity(query: str, text: str) -> float:
        """Tinh diem tuong dong tu khoa BM25/Jaccard don gian hoa."""
        if not query or not text:
            return 0.0

        q_tokens = set(re.findall(r"\w+", query.lower()))
        t_tokens = set(re.findall(r"\w+", text.lower()))

        if not q_tokens or not t_tokens:
            return 0.0

        intersection = len(q_tokens.intersection(t_tokens))
        union = len(q_tokens.union(t_tokens))
        return round(float(intersection) / float(union) if union > 0 else 0.0, 4)

    @staticmethod
    def compute_offline_semantic_similarity(text1: str, text2: str) -> float:
        """
        Mo phong semantic cosine similarity tren vector offline
        dua tren n-gram character/word hash phu hop moi truong khong mang.
        """
        if not text1 or not text2:
            return 0.0

        def get_char_ngrams(s: str, n=3):
            s_clean = s.lower().strip()
            return [s_clean[i:i+n] for i in range(max(len(s_clean) - n + 1, 1))]

        ng1 = set(get_char_ngrams(text1, 3))
        ng2 = set(get_char_ngrams(text2, 3))

        inter = len(ng1.intersection(ng2))
        norm = math.sqrt(len(ng1)) * math.sqrt(len(ng2))
        return round(float(inter) / norm if norm > 0 else 0.0, 4)

    @classmethod
    def search(
        cls,
        db: Session,
        workspace_id: str,
        brief: BrandBriefVersion,
        query: Optional[str] = None,
        intent_group: Optional[str] = None,
        need_category: Optional[str] = None,
        limit: int = 10,
        provider_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Thuc thi tim kiem lai trong workspace.
        P07-03: Loc rights_basis != NOT_GRANTED va tra co synthetic.
        P07-04: Loc NeedSignal theo intent_group va need_category.
        P07-08: Loai bo ket qua hoan toan khong lien quan truoc khi ranking.
        P07-10: Gioi han limit an toan trong mien [1, 100].
        """
        # P07-10: Chuan hoa limit
        safe_limit = max(1, min(int(limit) if limit is not None else 10, 100))

        # 1. Bo loc cau truc (Structured Filter) - P07-03: chan purged va rights_basis=NOT_GRANTED
        db_query = db.query(SourceRecord).filter(
            SourceRecord.workspace_id == workspace_id,
            SourceRecord.is_purged.is_(False),
            SourceRecord.rights_basis != "NOT_GRANTED"
        )
        if provider_ids:
            db_query = db_query.filter(SourceRecord.provider_id.in_(provider_ids))

        # P07-04: Loc theo intent_group va need_category qua NeedSignal
        if intent_group or need_category:
            ns_query = db.query(NeedSignal).filter(NeedSignal.workspace_id == workspace_id)
            if intent_group:
                ns_query = ns_query.filter(NeedSignal.intent_group == intent_group)
            if need_category:
                ns_query = ns_query.filter(NeedSignal.need_category == need_category)
            
            matching_signals = ns_query.all()
            if not matching_signals:
                return []
            
            matching_exc_ids = [ns.evidence_excerpt_id for ns in matching_signals]
            matching_excerpts = db.query(EvidenceExcerpt).filter(EvidenceExcerpt.id.in_(matching_exc_ids)).all()
            matching_source_ids = list(set([e.source_record_id for e in matching_excerpts if e.source_record_id]))
            db_query = db_query.filter(SourceRecord.id.in_(matching_source_ids))

        records = db_query.all()
        if not records:
            return []

        search_query = query or brief.objective
        results = []

        for rec in records:
            # Thu thap trich doan va snapshots cua ban ghi
            excerpts = db.query(EvidenceExcerpt).filter(
                EvidenceExcerpt.source_record_id == rec.id
            ).all()
            excerpt_texts = [e.excerpt_text for e in excerpts]
            combined_excerpt = " ".join(excerpt_texts)
            content_text = f"{rec.title or ''} {rec.caption or ''} {combined_excerpt}".strip()

            # Lay snapshots
            snaps = db.query(MetricSnapshot).filter(
                MetricSnapshot.source_record_id == rec.id
            ).all()
            snap_dicts = [
                {
                    "observed_at": s.observed_at,
                    "view_count": s.view_count,
                    "like_count": s.like_count
                }
                for s in snaps
            ]

            # P07-05: Xac dinh observed_vs_inferred trung thuc
            obs_type = "OBSERVED_DIRECT"
            ev_tier = "LIMITED_SIGNAL"
            if excerpts:
                # Kiem tra xem co NeedSignal nao lien ket voi excerpt khong
                exc_ids = [e.id for e in excerpts]
                ns_list = db.query(NeedSignal).filter(NeedSignal.evidence_excerpt_id.in_(exc_ids)).all()
                if ns_list:
                    if all(ns.observed_vs_inferred == "INFERRED_UNVERIFIED" for ns in ns_list):
                        obs_type = "INFERRED_UNVERIFIED"
                        ev_tier = "LIMITED_SIGNAL"
                    else:
                        obs_type = "OBSERVED_DIRECT"
                        ev_tier = "EVIDENCE_BACKED"
                else:
                    ev_tier = "EVIDENCE_BACKED"

            # 2. Cham diem tuong minh Explicit Scoring (5 thanh phan + Veto)
            score_data = ExplicitScorer.score_candidate(
                candidate_title=rec.title or "",
                content_excerpt=content_text,
                topics_included=brief.topics_included,
                topics_excluded=brief.topics_excluded,
                objective=brief.objective,
                target_audience=brief.target_audience,
                production_limits=brief.production_limits,
                evidence_tier=ev_tier,
                observed_vs_inferred=obs_type,
                snapshots=snap_dicts
            )

            # Bo loc bat buoc: Neu dính Veto, loai bo ngay lap tuc khoi ket qua
            if score_data["veto_violation"]:
                continue

            # 3. Tinh Full-text score & Semantic score
            ft_score = cls.compute_text_similarity(search_query, content_text)
            sem_score = cls.compute_offline_semantic_similarity(search_query, content_text)

            # P07-08: Loai bo ket qua hoan toan khong lien quan
            # Neu khong trung tu khoa nao va semantic score rat thap (< 0.12) dong thoi khong co tu khoa objective
            has_obj_match = any(inc.lower() in content_text.lower() for inc in (brief.topics_included or []))
            if ft_score == 0 and sem_score < 0.12 and not has_obj_match:
                continue

            # 4. Tinh Hybrid Rank Score
            # 50% Explicit Quality Score (0-10 -> quy doi 0-1) + 30% Full-text + 20% Semantic
            norm_explicit = score_data["overall_score"] / 10.0
            hybrid_score = round(norm_explicit * 0.50 + ft_score * 0.30 + sem_score * 0.20, 4)

            # P07-03: Bao toan co synthetic
            results.append({
                "id": rec.id,
                "title": rec.title or "N/A",
                "excerpt": content_text[:300],
                "hybrid_score": hybrid_score,
                "scoring_breakdown": score_data,
                "source_url": rec.canonical_url,
                "evidence_tier": ev_tier,
                "synthetic": getattr(rec, "synthetic", False)
            })

        # Sap xep giam dan theo hybrid_score
        results.sort(key=lambda r: r["hybrid_score"], reverse=True)
        return results[:safe_limit]
