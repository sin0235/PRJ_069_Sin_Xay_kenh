# Understanding Service (P06)
# Ket noi PromptInjectionGuard, NeedExtractor, TopicClusterer va AsrEvaluator

import json
from typing import List, Dict, Any, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from src.models.entities import (
    EvidenceExcerpt,
    NeedSignal,
    TopicCluster,
    TopicClusterSignal,
    SourceRecord
)
from src.schemas.contracts import EvidenceExcerptCreate
from src.modules.understanding.prompt_injection_guard import PromptInjectionGuard
from src.modules.understanding.need_extractor import NeedExtractor
from src.modules.understanding.topic_clusterer import TopicClusterer
from src.modules.understanding.asr_evaluator import AsrEvaluator

class UnderstandingService:
    @staticmethod
    def extract_and_store_signals(
        db: Session,
        workspace_id: str,
        data: EvidenceExcerptCreate
    ) -> Tuple[EvidenceExcerpt, List[NeedSignal], bool, Optional[str]]:
        """
        Tiep nhan trich doan, kiem tra Prompt Injection, luu tru an toan,
        boc tach cac tin hieu nhu cau va luu NeedSignal vao co so du lieu.
        """
        # 1. Kiem tra SourceRecord ton tai trong workspace
        source_rec = db.query(SourceRecord).filter(
            SourceRecord.id == data.source_record_id,
            SourceRecord.workspace_id == workspace_id
        ).first()
        if not source_rec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "RESOURCE_NOT_FOUND", "message": f"SourceRecord {data.source_record_id} không tồn tại trong workspace {workspace_id}"}
            )

        # P06-03: Chan nguon da bi purge hoac quyen bi thu hoi / khong duoc cap
        if getattr(source_rec, "is_purged", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "SOURCE_PURGED", "message": "Nguồn đã bị purge, không thể tiếp nhận trích đoạn hay bóc tách tín hiệu."}
            )
        if getattr(source_rec, "rights_basis", None) == "NOT_GRANTED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "RIGHTS_NOT_GRANTED", "message": "Nguồn chưa được cấp quyền sử dụng hợp lệ."}
            )

        # P06-06: Kiem tra tinh chan thuc cua trich doan loai CAPTION voi noi dung nguon
        if data.excerpt_type == "CAPTION":
            source_cap = (source_rec.caption or "").strip()
            req_text = data.excerpt_text.strip()
            if not source_cap:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error_code": "CAPTION_NOT_IN_SOURCE", "message": "Nguồn không có caption để trích dẫn."}
                )
            if req_text.lower() not in source_cap.lower() and source_cap.lower() not in req_text.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error_code": "CAPTION_NOT_IN_SOURCE", "message": "Nội dung caption trích dẫn không khớp với caption thực tế của nguồn."}
                )

        # 2. Prompt Injection Guard (T061)
        security_check = PromptInjectionGuard.inspect_and_sanitize(data.excerpt_text)
        has_injection_risk = security_check["has_injection_risk"]
        sanitized_text = security_check["sanitized_text"]
        warning = None
        if has_injection_risk:
            warning = f"Phát hiện mẫu lệnh độc hại ({', '.join(security_check['detected_patterns'])}). Văn bản được lưu trữ an toàn dưới dạng dữ liệu thô thụ động; cấm thực thi công cụ."

        # P06-02: Chi coi has_official_analytics la True khi co analytics_report_id hop le
        has_verified_analytics = False
        if getattr(data, "has_official_analytics", False):
            rpt_id = getattr(data, "analytics_report_id", None)
            if rpt_id and len(str(rpt_id).strip()) >= 5:
                has_verified_analytics = True

        # P06-07: Idempotency Deduplication - Tranh gui lai lam tang gia so luong tin hieu
        existing_excerpt = db.query(EvidenceExcerpt).filter(
            EvidenceExcerpt.workspace_id == workspace_id,
            EvidenceExcerpt.source_record_id == data.source_record_id,
            EvidenceExcerpt.excerpt_type == data.excerpt_type,
            EvidenceExcerpt.excerpt_text == sanitized_text
        ).first()

        if existing_excerpt:
            existing_signals = db.query(NeedSignal).filter(
                NeedSignal.evidence_excerpt_id == existing_excerpt.id
            ).all()
            # Neu lan nay co bao cao phan tich chinh thuc -> nang cap cac tin hieu suy luan len OBSERVED_DIRECT
            if has_verified_analytics:
                for s in existing_signals:
                    if s.observed_vs_inferred == "INFERRED_UNVERIFIED":
                        s.observed_vs_inferred = "OBSERVED_DIRECT"
                        s.confidence_score = 0.95
                        s.demographic_inferences_json = json.dumps([{
                            "claim": s.quote_text,
                            "status": "VERIFIED_BY_ANALYTICS",
                            "reason": f"Backed by verified analytics report: {data.analytics_report_id}"
                        }], ensure_ascii=False)
                db.commit()
                for s in existing_signals:
                    db.refresh(s)
            return existing_excerpt, existing_signals, has_injection_risk, warning

        # 3. Tao va luu EvidenceExcerpt
        excerpt = EvidenceExcerpt(
            workspace_id=workspace_id,
            source_record_id=data.source_record_id,
            excerpt_text=sanitized_text,
            excerpt_type=data.excerpt_type,
            author_id=data.author_id,
            is_sanitized=True
        )
        db.add(excerpt)
        db.flush()

        # 4. Boc tach tin hieu nhu cau (T060, T062)
        extracted_dicts = NeedExtractor.extract(
            text=sanitized_text,
            has_official_analytics=has_verified_analytics
        )

        signals = []
        for d in extracted_dicts:
            sig = NeedSignal(
                workspace_id=workspace_id,
                evidence_excerpt_id=excerpt.id,
                intent_group=d["intent_group"],
                need_category=d["need_category"],
                signal_text=d["signal_text"],
                quote_text=d["quote_text"],
                observed_vs_inferred=d["observed_vs_inferred"],
                confidence_score=d["confidence_score"],
                demographic_inferences_json=d["demographic_inferences_json"]
            )
            db.add(sig)
            signals.append(sig)

        db.commit()
        db.refresh(excerpt)
        for s in signals:
            db.refresh(s)

        return excerpt, signals, has_injection_risk, warning

    @staticmethod
    def run_clustering(
        db: Session,
        workspace_id: str,
        enabled: bool = True,
        intent_group: Optional[str] = None
    ) -> List[TopicCluster]:
        """Gom cum chu de trong workspace (T060), loai tru nguon purged (P06-03)."""
        clusterer = TopicClusterer(enabled=enabled)
        return clusterer.cluster_workspace_signals(
            db=db,
            workspace_id=workspace_id,
            intent_group_filter=intent_group
        )

    @staticmethod
    def get_clusters(db: Session, workspace_id: str) -> List[TopicCluster]:
        """Lay danh sach cac cum chu de kem tin hieu ben trong, loai bo nguon da bi purge (P06-03)."""
        clusters = db.query(TopicCluster).options(
            joinedload(TopicCluster.signals).joinedload(TopicClusterSignal.need_signal)
        ).filter(
            TopicCluster.workspace_id == workspace_id
        ).all()
        # Loc bo cac signals thuoc ve source da bi purge
        valid_clusters = []
        for cl in clusters:
            filtered_signals = []
            for tcs in cl.signals:
                sig = tcs.need_signal
                if sig and sig.evidence_excerpt and sig.evidence_excerpt.source_record:
                    src = sig.evidence_excerpt.source_record
                    if not getattr(src, "is_purged", False) and getattr(src, "rights_basis", None) != "NOT_GRANTED":
                        filtered_signals.append(tcs)
            cl.signals = filtered_signals
            valid_clusters.append(cl)
        return valid_clusters

    @staticmethod
    def get_signals(
        db: Session,
        workspace_id: str,
        intent_group: Optional[str] = None,
        need_category: Optional[str] = None
    ) -> List[NeedSignal]:
        """Truy van danh sach tin hieu nhu cau, loai bo nguon da bi purge hoac ungranted (P06-03)."""
        query = (
            db.query(NeedSignal)
            .join(EvidenceExcerpt, NeedSignal.evidence_excerpt_id == EvidenceExcerpt.id)
            .join(SourceRecord, EvidenceExcerpt.source_record_id == SourceRecord.id)
            .filter(
                NeedSignal.workspace_id == workspace_id,
                SourceRecord.is_purged.is_(False),
                SourceRecord.rights_basis != "NOT_GRANTED"
            )
        )
        if intent_group:
            query = query.filter(NeedSignal.intent_group == intent_group)
        if need_category:
            query = query.filter(NeedSignal.need_category == need_category)
        return query.all()

    @staticmethod
    def check_asr_status(licensed_audio_count: int = 0) -> Dict[str, Any]:
        """Kiem tra trang thai ASR (T063 / P06-01)."""
        return AsrEvaluator.get_asr_capability_status(licensed_audio_count=licensed_audio_count)

    @staticmethod
    def evaluate_asr(
        references: List[str],
        hypotheses: List[str],
        domain_terms: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Chay danh gia WER tren tap du lieu cap phep (T063)."""
        return AsrEvaluator.evaluate_transcripts(
            references=references,
            hypotheses=hypotheses,
            domain_terms=domain_terms
        )

understanding_service = UnderstandingService()
