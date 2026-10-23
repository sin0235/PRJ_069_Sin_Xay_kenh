# Service dieu phoi y tuong: IdeationService (P08, P08-02, P08-03, P08-04, P08-06, P08-07, P08-10, Gate 4 LLM Integration)
import json
import uuid
import math
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from datetime import datetime, timezone

from src.config import settings as default_settings, Settings
from src.models.entities import (
    IdeaCard, BrandBriefVersion, EvidenceExcerpt, SourceRecord,
    AuditEvent, NeedSignal, GoldCandidate
)
from src.schemas.contracts import (
    IdeaCardCreate, IdeaCardOut, IdeaCardVerifyRequest,
    IdeaCardVerifyResponse, IdeaGenerationRequest,
    IdeaGenerationResponse, IdeaReviewRequest,
    ReviewAuditItemOut
)
from src.modules.ideation.verifier import idea_verifier
from src.modules.ideation.duplicate_detector import duplicate_detector
from src.modules.ideation.generator import ideation_generator, SchemaValidationError
from src.modules.staging_reliability.budget_guard import budget_guard
from src.modules.platform_config.service import platform_config_service
from src.modules.llm.client import (
    LLMClient,
    CompletionResult,
    LLMClientError,
    LLMConfigError,
    LLMTimeoutError,
    LLMNetworkError,
    LLMResponseError,
)

logger = logging.getLogger("sin_content_api.ideation_service")

class IdeationService:
    """
    Dieu phoi toan bo luong sinh, xac thuc va quan ly vong doi the y tuong:
    - Sinh the y tuong co can cu trich dan (Grounded Ideation).
    - Tu choi triet de cac trich dan bia dat khong ton tai hoac sai workspace.
    - Kiem soat che do INSUFFICIENT_EVIDENCE / HYPOTHESIS.
    - Phat hien va canh bao trung lap voi cac y tuong da duyet.
    - Hang doi phe duyet (Review Queue: APPROVE, REJECT, REQUEST_EVIDENCE).
    - Bao ve nguon du lieu (purged, rights_basis, synthetic).
    - Tich hop LLM 9Router Gateway voi khoa ngan sach nguyen tu va Idempotency (Gate 4).
    """

    def __init__(self, settings: Optional[Settings] = None):
        self._settings = settings

    @property
    def settings(self) -> Settings:
        return self._settings or default_settings

    def generate_ideas(
        self,
        db: Session,
        workspace_id: str,
        user_id: str,
        req: IdeaGenerationRequest,
        idempotency_key: Optional[str] = None,
        llm_client: Optional[LLMClient] = None,
        settings: Optional[Settings] = None
    ) -> IdeaGenerationResponse:
        cfg = settings or self.settings

        # 1. Kiem tra brief version va workspace (P08-04)
        brief = db.query(BrandBriefVersion).filter(
            BrandBriefVersion.id == req.brief_version_id,
            BrandBriefVersion.workspace_id == workspace_id
        ).first()

        if not brief:
            raise HTTPException(status_code=404, detail="BrandBriefVersion not found in workspace")
        if getattr(brief, "status", None) != "APPROVED":
            raise HTTPException(status_code=422, detail="BrandBriefVersion must be APPROVED before ideation generation")

        # 2. Truy van bang chung co san trong workspace (P08-02: loai bo purged va rights_basis=NOT_GRANTED)
        query = db.query(EvidenceExcerpt).join(
            SourceRecord, EvidenceExcerpt.source_record_id == SourceRecord.id
        ).filter(
            EvidenceExcerpt.workspace_id == workspace_id,
            SourceRecord.is_purged.is_(False),
            SourceRecord.rights_basis != "NOT_GRANTED"
        )

        # P08-03: Loc theo candidate_ids neu co chi dinh
        if req.candidate_ids:
            candidates = db.query(GoldCandidate).filter(
                GoldCandidate.id.in_(req.candidate_ids),
                GoldCandidate.workspace_id == workspace_id
            ).all()
            if not candidates:
                query = query.filter(EvidenceExcerpt.id == "NONE_MATCHING")
            else:
                cand_urls = [c.source_url for c in candidates if c.source_url]
                if cand_urls:
                    query = query.filter(SourceRecord.canonical_url.in_(cand_urls))

        # P08-03: Loc theo selected_need_categories neu co chi dinh
        if req.selected_need_categories:
            need_signals = db.query(NeedSignal).filter(
                NeedSignal.workspace_id == workspace_id,
                NeedSignal.need_category.in_(req.selected_need_categories)
            ).all()
            if not need_signals:
                query = query.filter(EvidenceExcerpt.id == "NONE_MATCHING")
            else:
                matching_exc_ids = [ns.evidence_excerpt_id for ns in need_signals]
                query = query.filter(EvidenceExcerpt.id.in_(matching_exc_ids))

        excerpts_db = query.all()
        excerpts_data = []
        for exc in excerpts_db:
            excerpts_data.append({
                "id": exc.id,
                "excerpt_text": exc.excerpt_text,
                "source_url": exc.source_record.canonical_url if exc.source_record else None,
                "excerpt_type": exc.excerpt_type,
                "synthetic": getattr(exc.source_record, "synthetic", False) if exc.source_record else False
            })

        # 3. Kiem tra co so bang chung (T082)
        if not excerpts_data:
            if not req.allow_hypotheses:
                source_lbl = "llm_router" if cfg.is_llm_enabled else "offline_template"
                return IdeaGenerationResponse(
                    brief_version_id=req.brief_version_id,
                    total_generated=0,
                    confidence_tier_summary={"EVIDENCE_BACKED": 0, "LIMITED_SIGNAL": 0, "HYPOTHESIS": 0},
                    ideas=[],
                    status="INSUFFICIENT_EVIDENCE",
                    message="INSUFFICIENT_EVIDENCE: Không tìm thấy bằng chứng thực tế quan sát được trong workspace và allow_hypotheses=False. Bật allow_hypotheses=True nếu muốn tạo giả thuyết sáng tạo.",
                    generation_source=source_lbl,
                    cost_units=0.0
                )

        # 4. Phan nhanh: Uu tien settings/llm_client neu caller truyen tuong minh, nguoc lai doc tu Database Singleton
        runtime_creds = None
        if settings is None:
            runtime_creds = platform_config_service.get_runtime_llm_credentials(db)

        if llm_client is not None:
            is_llm_active = getattr(llm_client, "is_enabled", True) and bool(getattr(llm_client, "api_key", ""))
        elif runtime_creds is not None:
            is_llm_active = bool(runtime_creds.get("is_enabled"))
        else:
            is_llm_active = cfg.is_llm_enabled

        if not is_llm_active:
            # === CHE DO OFFLINE TEMPLATE HIEN TAI ===
            raw_ideas = ideation_generator.generate_grounded_ideas_offline(
                brief_id=brief.id,
                brand_name=brief.brand_name,
                brief_objective=brief.objective,
                excerpts=excerpts_data,
                num_ideas=req.num_ideas,
                allow_hypotheses=req.allow_hypotheses
            )

            created_cards: List[IdeaCardOut] = []
            tier_counts = {"EVIDENCE_BACKED": 0, "LIMITED_SIGNAL": 0, "HYPOTHESIS": 0}

            for item in raw_ideas:
                card_create = IdeaCardCreate(
                    brief_version_id=brief.id,
                    title=item["title"],
                    target_need=item["target_need"],
                    hook=item["hook"],
                    content_angle=item["content_angle"],
                    confidence_tier=item["confidence_tier"],
                    evidence_excerpt_ids=item["evidence_excerpt_ids"],
                    citations=item.get("citations", []),
                    overall_score=item["overall_score"],
                    allow_hypotheses=req.allow_hypotheses
                )

                verif = idea_verifier.verify(db, workspace_id, card_create, brief)
                if not verif.is_valid:
                    continue

                has_dup, dup_warn, sim_val, dup_id = duplicate_detector.check_duplicate(
                    db, workspace_id, card_create.hook, card_create.content_angle
                )

                is_synthetic = False
                for eid in card_create.evidence_excerpt_ids:
                    matching_exc = next((e for e in excerpts_data if e["id"] == eid), None)
                    if matching_exc and matching_exc.get("synthetic"):
                        is_synthetic = True
                        break

                card_db = IdeaCard(
                    workspace_id=workspace_id,
                    brief_version_id=brief.id,
                    title=card_create.title,
                    target_need=card_create.target_need,
                    hook=card_create.hook,
                    content_angle=card_create.content_angle,
                    confidence_tier=card_create.confidence_tier,
                    status=verif.suggested_status,
                    overall_score=card_create.overall_score,
                    evidence_excerpt_ids_json=json.dumps(card_create.evidence_excerpt_ids),
                    citations_json=json.dumps([c.model_dump() for c in card_create.citations] if card_create.citations else []),
                    duplicate_warning=dup_warn,
                    creator_id=user_id,
                    version=1,
                    synthetic=is_synthetic
                )
                db.add(card_db)
                db.flush()

                tier_counts[card_create.confidence_tier] = tier_counts.get(card_create.confidence_tier, 0) + 1
                created_cards.append(self._to_card_out(card_db))

            db.commit()

            audit = AuditEvent(
                workspace_id=workspace_id,
                actor_id=user_id,
                event_type="IDEA_GENERATION",
                details=json.dumps({
                    "brief_id": brief.id,
                    "total_generated": len(created_cards),
                    "allow_hypotheses": req.allow_hypotheses,
                    "generation_source": "offline_template"
                })
            )
            db.add(audit)
            db.commit()

            return IdeaGenerationResponse(
                brief_version_id=brief.id,
                total_generated=len(created_cards),
                confidence_tier_summary=tier_counts,
                ideas=created_cards,
                status="SUCCESS",
                message=f"Đã sinh {len(created_cards)} ý tưởng có căn cứ kiểm chứng vững chắc (Template offline).",
                generation_source="offline_template",
                cost_units=0.0
            )

        # === CHE DO LLM 9ROUTER GATEWAY (Gate 4) ===
        # 4.1. Kiem tra bat buoc Idempotency-Key
        if not idempotency_key or not idempotency_key.strip():
            raise HTTPException(
                status_code=400,
                detail="Chế độ LLM bắt buộc phải có header 'Idempotency-Key' để đảm bảo tính lũy đẳng."
            )
        idempotency_key = idempotency_key.strip()
        if len(idempotency_key) > 100:
            raise HTTPException(
                status_code=400,
                detail="Idempotency-Key không được vượt quá 100 ký tự."
            )

        # 4.2. Xac dinh bang gia va tham so van hanh tu Database Singleton hoac Settings
        pricing_input = runtime_creds.get("input_usd_per_1k_tokens", cfg.llm_input_usd_per_1k_tokens) if runtime_creds else cfg.llm_input_usd_per_1k_tokens
        pricing_output = runtime_creds.get("output_usd_per_1k_tokens", cfg.llm_output_usd_per_1k_tokens) if runtime_creds else cfg.llm_output_usd_per_1k_tokens
        budget_units_ratio = runtime_creds.get("budget_units_per_usd", cfg.llm_budget_units_per_usd) if runtime_creds else cfg.llm_budget_units_per_usd
        max_output_tok = runtime_creds.get("max_output_tokens", cfg.llm_max_output_tokens) if runtime_creds else cfg.llm_max_output_tokens

        if pricing_input <= 0 or pricing_output <= 0:
            raise HTTPException(
                status_code=422,
                detail="Cấu hình bảng giá LLM chưa hợp lệ (input hoặc output token price <= 0). Không thể ước lượng chi phí."
            )

        # 4.3. Xay dung prompt va tinh toan uoc luong chi phi bao thu
        messages = ideation_generator.build_ideation_prompt(
            brand_name=brief.brand_name,
            brief_objective=brief.objective,
            voice_description=brief.voice_description,
            target_audience=brief.target_audience,
            topics_included=brief.topics_included,
            topics_excluded=brief.topics_excluded,
            excerpts=excerpts_data,
            num_ideas=req.num_ideas,
            allow_hypotheses=req.allow_hypotheses
        )

        prompt_utf8_bytes = sum(len(str(m.get("content", "")).encode("utf-8")) for m in messages)
        est_input_tokens = prompt_utf8_bytes
        est_output_tokens = max_output_tok
        est_cost_usd = (est_input_tokens / 1000.0) * pricing_input + (est_output_tokens / 1000.0) * pricing_output
        est_units = round(est_cost_usd * budget_units_ratio, 4)

        if not math.isfinite(est_units) or est_units <= 0:
            raise HTTPException(
                status_code=422,
                detail=f"Phí ước lượng cho tác vụ LLM ({est_units} units) không hợp lệ (phải là số thực dương hữu hạn). Vui lòng kiểm tra lại cấu hình bảng giá và hệ số quy đổi ngân sách."
            )

        # 4.4. Kiem tra tran chi phi max_cost_usd truoc khi giu cho
        if est_cost_usd > req.max_cost_usd:
            raise HTTPException(
                status_code=422,
                detail=f"Chi phí ước lượng ({est_cost_usd:.4f} USD) vượt quá trần ngân sách cho phép của yêu cầu ({req.max_cost_usd:.4f} USD)."
            )

        # 4.5. Giu cho ngan sach nguyen tu (Atomic Budget Reservation)
        task_id = f"llm_idea_{uuid.uuid4().hex[:8]}"
        reserve_resp = budget_guard.reserve_budget(
            db=db,
            workspace_id=workspace_id,
            task_id=task_id,
            idempotency_key=idempotency_key,
            action_type="LLM_IDEATION",
            estimated_units=est_units
        )

        if reserve_resp.status == "IDEMPOTENT_HIT":
            raise HTTPException(
                status_code=409,
                detail=f"Idempotency-Key '{idempotency_key}' đã được sử dụng trước đó. Vui lòng kiểm tra sổ cái chi phí (ledger) trước khi gửi yêu cầu mới."
            )

        if reserve_resp.status != "RESERVED":
            raise HTTPException(
                status_code=402,
                detail=f"Ngân sách không khả dụng: {reserve_resp.message}"
            )

        ledger_id = reserve_resp.ledger_id
        client = llm_client or (LLMClient(runtime_config=runtime_creds) if runtime_creds else LLMClient(settings=cfg))
        ledger_committed = False

        # 4.6. Goi upstream va xu ly voi co che hoan ngan sach (Safe Rollback)
        try:
            completion = client.complete(messages, max_tokens=max_output_tok)

            # Tinh toan chi phi thuc te: chi tin cay khi usage tra ve du cap nguyen khong am
            if completion.usage_valid:
                actual_cost_usd = (completion.prompt_tokens / 1000.0) * pricing_input + (completion.completion_tokens / 1000.0) * pricing_output
                actual_units = round(actual_cost_usd * budget_units_ratio, 4)
                vendor_reported_units = actual_units
            else:
                actual_cost_usd = est_cost_usd
                actual_units = est_units
                vendor_reported_units = None

            # Kiem tra neu nha cung cap da tinh phi vuot muc cho phep (Overrun check)
            # Hoac completion_tokens vuot qua max_output_tokens da cau hinh
            if actual_cost_usd > req.max_cost_usd or completion.completion_tokens > max_output_tok:
                # Nha cung cap da thuc hien va tinh phi vuot tran cho phep!
                # Ghi nhan chi phi thuc tra vao ledger kem canh bao doi soat (KHONG hoan phi vi nha cung cap da tinh phi)
                committed_ledger = budget_guard.commit_budget(
                    db=db,
                    workspace_id=workspace_id,
                    ledger_id=ledger_id,
                    actual_units=actual_units,
                    success=True,
                    output_artifact_id=f"overrun_rejected_{task_id}"
                )
                committed_ledger.discrepancy_alert = True
                if vendor_reported_units is None:
                    committed_ledger.vendor_reported_units = None

                ledger_committed = True

                audit = AuditEvent(
                    workspace_id=workspace_id,
                    actor_id=user_id,
                    event_type="LLM_BUDGET_OVERRUN_ALERT",
                    details=json.dumps({
                        "model": completion.model,
                        "actual_cost_usd": actual_cost_usd,
                        "max_cost_usd": req.max_cost_usd,
                        "actual_units": actual_units,
                        "prompt_tokens": completion.prompt_tokens,
                        "completion_tokens": completion.completion_tokens,
                        "ledger_id": ledger_id,
                        "message": "Chi phí thực tế của nhà cung cấp vượt quá hạn mức cho phép. Thẻ ý tưởng không được lưu."
                    })
                )
                db.add(audit)
                db.commit()

                raise HTTPException(
                    status_code=422,
                    detail=f"Chi phí thực tế từ LLM ({actual_cost_usd:.4f} USD, {actual_units} units) vượt quá hạn mức yêu cầu ({req.max_cost_usd:.4f} USD). Không thể lưu thẻ ý tưởng; chi phí đã được ghi nhận vào sổ cái để đối soát."
                )

            # Validate va sanitize JSON dau ra bang IdeaCardCreate
            allowed_excerpt_ids = {e["id"] for e in excerpts_data}
            raw_card_creates = ideation_generator.validate_and_sanitize_llm_ideas(
                raw_text=completion.content,
                brief_id=brief.id,
                num_ideas=req.num_ideas,
                allowed_excerpt_ids=allowed_excerpt_ids,
                allow_hypotheses=req.allow_hypotheses
            )

            if not raw_card_creates:
                if not req.allow_hypotheses:
                    raise HTTPException(
                        status_code=422,
                        detail="LLM không tạo được ý tưởng có căn cứ từ danh sách bằng chứng được cung cấp."
                    )

            cards_to_persist = []
            tier_counts = {"EVIDENCE_BACKED": 0, "LIMITED_SIGNAL": 0, "HYPOTHESIS": 0}

            # Dua tung the qua bo kiem chung doc lap (IdeaVerifier)
            for card_create in raw_card_creates:
                verif = idea_verifier.verify(db, workspace_id, card_create, brief)
                if not verif.is_valid:
                    continue

                has_dup, dup_warn, sim_val, dup_id = duplicate_detector.check_duplicate(
                    db, workspace_id, card_create.hook, card_create.content_angle
                )

                is_synthetic = False
                for eid in card_create.evidence_excerpt_ids:
                    matching_exc = next((e for e in excerpts_data if e["id"] == eid), None)
                    if matching_exc and matching_exc.get("synthetic"):
                        is_synthetic = True
                        break

                card_db = IdeaCard(
                    workspace_id=workspace_id,
                    brief_version_id=brief.id,
                    title=card_create.title,
                    target_need=card_create.target_need,
                    hook=card_create.hook,
                    content_angle=card_create.content_angle,
                    confidence_tier=card_create.confidence_tier,
                    status=verif.suggested_status,
                    overall_score=card_create.overall_score,
                    evidence_excerpt_ids_json=json.dumps(card_create.evidence_excerpt_ids),
                    citations_json=json.dumps([c.model_dump() for c in card_create.citations] if card_create.citations else []),
                    duplicate_warning=dup_warn,
                    creator_id=user_id,
                    version=1,
                    synthetic=is_synthetic
                )
                # Luu vao danh sach bo nho, CHUA db.add va CHUA db.flush de tranh commit the do dang
                cards_to_persist.append((card_db, card_create.confidence_tier))

            if not cards_to_persist:
                raise HTTPException(
                    status_code=422,
                    detail="Toàn bộ ý tưởng do LLM sinh ra đã bị bộ kiểm chứng độc lập (IdeaVerifier) từ chối do vi phạm quy tắc an toàn hoặc trích dẫn."
                )

            # Tat ca da hop le -> Tien hanh luu the va commit budget theo trinh tu giao dich nhat quan
            created_cards: List[IdeaCardOut] = []
            for card_db, conf_tier in cards_to_persist:
                db.add(card_db)
                tier_counts[conf_tier] = tier_counts.get(conf_tier, 0) + 1

            # Commit ngan sach thanh cong (lenh nay commit ca cards va ledger dong thoi)
            committed_ledger = budget_guard.commit_budget(
                db=db,
                workspace_id=workspace_id,
                ledger_id=ledger_id,
                actual_units=actual_units,
                success=True,
                output_artifact_id=f"idea_batch_{task_id}"
            )
            if vendor_reported_units is None:
                committed_ledger.vendor_reported_units = None
                db.commit()

            ledger_committed = True

            for card_db, _ in cards_to_persist:
                created_cards.append(self._to_card_out(card_db))

            # Ghi nhat ky kiem toan audit event
            audit = AuditEvent(
                workspace_id=workspace_id,
                actor_id=user_id,
                event_type="IDEA_GENERATION_LLM",
                details=json.dumps({
                    "model": completion.model,
                    "generation_source": "llm_router",
                    "prompt_tokens": completion.prompt_tokens,
                    "completion_tokens": completion.completion_tokens,
                    "cost_units": actual_units,
                    "total_generated": len(created_cards),
                    "ledger_id": ledger_id,
                    "needs_reconciliation": (vendor_reported_units is None)
                })
            )
            db.add(audit)
            db.commit()

            return IdeaGenerationResponse(
                brief_version_id=brief.id,
                total_generated=len(created_cards),
                confidence_tier_summary=tier_counts,
                ideas=created_cards,
                status="SUCCESS",
                message=f"Đã sinh {len(created_cards)} ý tưởng thành công qua LLM Gateway.",
                generation_source="llm_router",
                cost_units=actual_units
            )

        except Exception as exc:
            # 1. Rollback toan bo pending changes trong session truoc khi lam bat cu thao tac nao
            db.rollback()

            # 2. Chi hoan tra phan giu cho neu ledger chua tung duoc commit
            if not ledger_committed:
                try:
                    budget_guard.commit_budget(
                        db=db,
                        workspace_id=workspace_id,
                        ledger_id=ledger_id,
                        actual_units=0.0,
                        success=False
                    )
                except Exception as refund_err:
                    logger.error("Lỗi khi hoàn trả reservation cho ledger_id=%s: %s", ledger_id, refund_err)

            if isinstance(exc, HTTPException):
                raise exc
            elif isinstance(exc, LLMTimeoutError):
                raise HTTPException(status_code=504, detail=f"LLM Gateway quá thời gian chờ: {exc.message}")
            elif isinstance(exc, (LLMResponseError, LLMNetworkError)):
                raise HTTPException(status_code=502, detail=f"Lỗi khi kết nối với LLM Gateway: {exc.message}")
            elif isinstance(exc, SchemaValidationError):
                raise HTTPException(status_code=422, detail=f"Lỗi cấu trúc phản hồi từ LLM: {exc.message}")
            else:
                raise HTTPException(status_code=500, detail=f"Lỗi nội bộ khi sinh ý tưởng qua LLM: {str(exc)}")

    def verify_idea_card(
        self,
        db: Session,
        workspace_id: str,
        req: IdeaCardVerifyRequest
    ) -> IdeaCardVerifyResponse:
        card = req.idea_card
        brief = db.query(BrandBriefVersion).filter(
            BrandBriefVersion.id == card.brief_version_id,
            BrandBriefVersion.workspace_id == workspace_id
        ).first()

        if not brief:
            raise HTTPException(status_code=404, detail="BrandBriefVersion not found in workspace")
        if getattr(brief, "status", None) != "APPROVED":
            raise HTTPException(status_code=422, detail="BrandBriefVersion must be APPROVED for verification")

        verif = idea_verifier.verify(db, workspace_id, card, brief)
        
        if verif.is_valid:
            has_dup, dup_warn, sim_val, dup_id = duplicate_detector.check_duplicate(
                db, workspace_id, card.hook, card.content_angle
            )
            if has_dup:
                verif.duplicate_warning = dup_warn

        card_preview = card.model_dump()
        if (not card.evidence_excerpt_ids and not card.citations) and card.allow_hypotheses:
            card_preview["confidence_tier"] = "HYPOTHESIS"

        return IdeaCardVerifyResponse(
            verification=verif,
            card_preview=card_preview
        )

    def _to_card_out(self, c: IdeaCard) -> IdeaCardOut:
        return IdeaCardOut(
            id=c.id,
            workspace_id=c.workspace_id,
            brief_version_id=c.brief_version_id,
            title=c.title,
            target_need=c.target_need,
            hook=c.hook,
            content_angle=c.content_angle,
            confidence_tier=c.confidence_tier,
            status=c.status,
            overall_score=c.overall_score,
            evidence_excerpt_ids=c.evidence_excerpt_ids,
            citations=getattr(c, "citations", []) or [],
            duplicate_warning=c.duplicate_warning,
            rejection_reason=c.rejection_reason,
            creator_id=getattr(c, "creator_id", None),
            version=getattr(c, "version", 1) or 1,
            review_reason=getattr(c, "review_reason", None),
            reviewed_by=getattr(c, "reviewed_by", None),
            reviewed_at=getattr(c, "reviewed_at", None),
            synthetic=c.synthetic,
            created_at=c.created_at
        )

    def review_idea_card(
        self,
        db: Session,
        workspace_id: str,
        user_id: str,
        idea_id: str,
        req: IdeaReviewRequest
    ) -> IdeaCardOut:
        card: Optional[IdeaCard] = db.query(IdeaCard).filter(
            IdeaCard.id == idea_id,
            IdeaCard.workspace_id == workspace_id
        ).first()

        if not card:
            raise HTTPException(status_code=404, detail="IdeaCard not found in workspace")

        if req.expected_status is None or req.expected_version is None:
            raise HTTPException(
                status_code=409,
                detail={
                    "error_code": "STALE_VERSION_CONFLICT",
                    "message": "Cần cung cấp expected_status và expected_version để kiểm soát phiên bản tương tranh.",
                    "current_status": card.status,
                    "current_version": getattr(card, "version", 1) or 1
                }
            )

        current_version = getattr(card, "version", 1) or 1
        if card.status != req.expected_status or current_version != req.expected_version:
            raise HTTPException(
                status_code=409,
                detail={
                    "error_code": "STALE_VERSION_CONFLICT",
                    "message": f"IdeaCard current version {current_version} (status '{card.status}') does not match expected v{req.expected_version} ('{req.expected_status}'). Stale approval conflict.",
                    "current_status": card.status,
                    "current_version": current_version
                }
            )

        reason_text = req.review_reason or req.reviewer_notes or ""
        prev_status = card.status
        target_status = card.status
        rejection_reason = None
        review_reason = reason_text

        if req.action == "APPROVE":
            if getattr(card, "creator_id", None) and card.creator_id == user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="SELF_APPROVAL_VIOLATION: Người tạo không được phép tự phê duyệt ý tưởng của chính mình (Quy tắc Bốn Mắt)."
                )
            if card.confidence_tier == "EVIDENCE_BACKED":
                if not card.evidence_excerpt_ids:
                    raise HTTPException(
                        status_code=422,
                        detail="Cannot approve idea card with EVIDENCE_BACKED confidence tier when no evidence excerpts are linked"
                    )
                for eid in card.evidence_excerpt_ids:
                    exc = db.query(EvidenceExcerpt).filter(
                        EvidenceExcerpt.id == eid,
                        EvidenceExcerpt.workspace_id == workspace_id
                    ).first()
                    if not exc:
                        raise HTTPException(
                            status_code=422,
                            detail=f"Cannot approve: evidence excerpt '{eid}' not found in workspace"
                        )
                    if exc.source_record and (getattr(exc.source_record, "is_purged", False) or getattr(exc.source_record, "rights_basis", "GRANTED") == "NOT_GRANTED"):
                        raise HTTPException(
                            status_code=422,
                            detail=f"Cannot approve: source record for excerpt '{eid}' is purged or rights not granted"
                        )

            brief = db.query(BrandBriefVersion).filter(
                BrandBriefVersion.id == card.brief_version_id,
                BrandBriefVersion.workspace_id == workspace_id
            ).first()
            if brief:
                banned_topics = [t.lower().strip() for t in (brief.topics_excluded or []) if t and t.strip()]
                combined = f"{card.title} {card.hook} {card.content_angle} {card.target_need}".lower()
                for b in banned_topics:
                    if b and b in combined:
                        raise HTTPException(
                            status_code=422,
                            detail=f"Cannot approve: card violates brand safety banned topic '{b}'"
                        )

            target_status = "APPROVED"
            rejection_reason = None
            review_reason = reason_text or "Approved by reviewer"
        elif req.action == "REJECT":
            target_status = "REJECTED"
            rejection_reason = reason_text or "Rejected by reviewer"
            review_reason = reason_text or "Rejected by reviewer"
        elif req.action == "REQUEST_EVIDENCE":
            target_status = "NEEDS_EVIDENCE"
            rejection_reason = reason_text or "Needs additional evidence"
            review_reason = reason_text or "Needs additional evidence"
        elif req.action == "REOPEN":
            target_status = "READY_FOR_REVIEW"
            review_reason = reason_text or "Reopened for review"

        now_utc = datetime.now(timezone.utc)
        new_version = current_version + 1

        updated_count = db.query(IdeaCard).filter(
            IdeaCard.id == idea_id,
            IdeaCard.workspace_id == workspace_id,
            IdeaCard.version == req.expected_version,
            IdeaCard.status == req.expected_status
        ).update({
            IdeaCard.status: target_status,
            IdeaCard.version: new_version,
            IdeaCard.reviewed_by: user_id,
            IdeaCard.reviewed_at: now_utc,
            IdeaCard.review_reason: review_reason,
            IdeaCard.rejection_reason: rejection_reason
        }, synchronize_session="fetch")

        if updated_count == 0:
            raise HTTPException(
                status_code=409,
                detail={
                    "error_code": "STALE_VERSION_CONFLICT",
                    "message": f"IdeaCard has been concurrently modified or version mismatch (expected v{req.expected_version}, status '{req.expected_status}').",
                    "current_status": card.status,
                    "current_version": getattr(card, "version", 1) or 1
                }
            )

        audit = AuditEvent(
            workspace_id=workspace_id,
            actor_id=user_id,
            event_type=f"IDEA_{req.action}",
            details=json.dumps({
                "idea_id": card.id,
                "action": req.action,
                "previous_status": prev_status,
                "new_status": target_status,
                "new_version": new_version,
                "review_reason": review_reason
            }, ensure_ascii=False)
        )
        db.add(audit)
        db.commit()
        db.refresh(card)

        return self._to_card_out(card)

    def get_idea_history(
        self,
        db: Session,
        workspace_id: str,
        idea_id: str
    ) -> List[ReviewAuditItemOut]:
        events = db.query(AuditEvent).filter(
            AuditEvent.workspace_id == workspace_id,
            AuditEvent.event_type.like("IDEA_%")
        ).order_by(AuditEvent.created_at.desc()).all()

        matched = []
        for e in events:
            try:
                d = json.loads(e.details or "{}")
                if d.get("idea_id") == idea_id:
                    matched.append(
                        ReviewAuditItemOut(
                            id=e.id,
                            workspace_id=e.workspace_id,
                            actor_id=e.actor_id,
                            event_type=e.event_type,
                            details=e.details,
                            created_at=e.created_at
                        )
                    )
            except Exception:
                pass

        return matched

    def list_idea_cards(
        self,
        db: Session,
        workspace_id: str,
        brief_version_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[IdeaCardOut]:
        query = db.query(IdeaCard).filter(IdeaCard.workspace_id == workspace_id)
        if brief_version_id:
            query = query.filter(IdeaCard.brief_version_id == brief_version_id)
        if status:
            query = query.filter(IdeaCard.status == status)

        cards = query.order_by(IdeaCard.created_at.desc()).limit(limit).all()
        return [self._to_card_out(c) for c in cards]

    def get_idea_card(
        self,
        db: Session,
        workspace_id: str,
        idea_id: str
    ) -> IdeaCardOut:
        card: Optional[IdeaCard] = db.query(IdeaCard).filter(
            IdeaCard.id == idea_id,
            IdeaCard.workspace_id == workspace_id
        ).first()

        if not card:
            raise HTTPException(status_code=404, detail="IdeaCard not found in workspace")

        return self._to_card_out(card)

ideation_service = IdeationService()
