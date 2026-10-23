# Service quan ly kich ban & kiem dinh tuyen bo: ScriptService (P09)
# Nang cap triet de cac loi Codex: P09-01, P09-02, P09-03, P09-04, P09-05, P09-06, P09-07, P09-08, P09-09
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from src.models.entities import (
    ScriptDraftVersion, IdeaCard, BrandBriefVersion, AllowedFact, AuditEvent
)
from src.schemas.contracts import (
    ScriptDraftCreate, ScriptDraftEditRequest, ScriptDraftOut,
    ScriptBlock, ClaimCheck, ScriptReviewRequest
)
from src.modules.scripts.claim_checker import claim_checker
from src.modules.scripts.timing_calculator import timing_calculator

def utc_now():
    return datetime.now(timezone.utc)

class ScriptService:
    """
    Service quan ly ban thao kich ban, phan canh va kiem dinh tuyen bo san pham:
    - Kiem dinh tuyen bo dinh luong (AllowedFact Check - T090, T091).
    - Bat buoc bat bien phien ban da duyet (Immutable Versioning on Edit - T092).
    - Kiem soat thoi luong phan canh va dung sai (Timing Tolerance & Hook Variants - T093).
    - Kiem tra dieu kien y tuong, brief va gioi han an toan thuong hieu (P09-07).
    """

    def _normalize_block(self, b: Any) -> ScriptBlock:
        if isinstance(b, dict):
            block_type = b.get('block_type') or b.get('type') or 'HOOK'
            narration = b.get('narration') or b.get('content') or b.get('text') or 'Phan canh kich ban'
            visual_cue = b.get('visual_cue') or b.get('visual') or 'Khung hinh tu nhien'
            duration_seconds = b.get('duration_seconds') or b.get('duration') or 3
            return ScriptBlock(
                block_type=block_type,
                narration=narration,
                visual_cue=visual_cue,
                duration_seconds=max(1, int(duration_seconds)),
                start_seconds=b.get('start_seconds'),
                end_seconds=b.get('end_seconds'),
            )
        return b

    def _normalize_claim(self, c: Any) -> ClaimCheck:
        if isinstance(c, dict):
            return ClaimCheck(
                claim_text=c.get('claim_text') or c.get('text') or 'Tuyen bo san pham',
                claim_type=c.get('claim_type') or 'QUANTITATIVE',
                allowed_fact_id=c.get('allowed_fact_id'),
                source_citation=c.get('source_citation'),
                verification_status=c.get('verification_status') or 'NEEDS_FACT_CHECK',
                notes=c.get('notes'),
            )
        return c

    def _to_script_out(self, s: ScriptDraftVersion) -> ScriptDraftOut:
        blocks_data = [self._normalize_block(b) for b in (s.blocks or [])]
        claims_data = [self._normalize_claim(c) for c in (s.claims or [])]
        
        return ScriptDraftOut(
            id=s.id,
            workspace_id=s.workspace_id,
            idea_id=s.idea_id,
            created_by_user_id=getattr(s, "created_by_user_id", None),
            version=s.version,
            title=s.title,
            target_duration_seconds=s.target_duration_seconds,
            actual_duration_seconds=s.actual_duration_seconds,
            duration_tolerance_passed=s.duration_tolerance_passed,
            hook_variants=s.hook_variants,
            blocks=blocks_data,
            claims=claims_data,
            status=s.status,
            blocking_claims_count=s.blocking_claims_count,
            approved_by_user_id=s.approved_by_user_id,
            approved_at=s.approved_at,
            rejection_reason=s.rejection_reason,
            created_at=s.created_at
        )

    def create_script_draft(
        self,
        db: Session,
        workspace_id: str,
        user_id: str,
        req: ScriptDraftCreate
    ) -> ScriptDraftOut:
        # 1. Kiem tra IdeaCard hop le trong workspace
        idea = db.query(IdeaCard).filter(
            IdeaCard.id == req.idea_id,
            IdeaCard.workspace_id == workspace_id
        ).first()

        if not idea:
            raise HTTPException(status_code=404, detail="IdeaCard not found in workspace")

        # P09-07: Kiem tra Brief lien ket va gioi han an toan thuong hieu
        brief = db.query(BrandBriefVersion).filter(
            BrandBriefVersion.id == idea.brief_version_id
        ).first()

        if brief:
            excluded_topics = brief.topics_excluded or []
            if isinstance(excluded_topics, str):
                try:
                    excluded_topics = json.loads(excluded_topics)
                except Exception:
                    excluded_topics = []

            all_script_text = (
                (req.title or "") + " " +
                " ".join(req.hook_variants or []) + " " +
                " ".join([b.narration or "" for b in req.blocks]) + " " +
                " ".join([b.visual_cue or "" for b in req.blocks])
            )
            for topic in (excluded_topics or []):
                if topic and topic.strip() and topic.strip().lower() in all_script_text.lower():
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={
                            "error_code": "SCRIPT_VIOLATES_BRAND_SAFETY",
                            "message": f"Kịch bản chứa chủ đề bị cấm theo Brand Safety: '{topic}'"
                        }
                    )

        # 2. Tinh toan thoi luong va dung sai phan canh (T093)
        blocks_dicts = [b.model_dump() for b in req.blocks]
        timing_info = timing_calculator.validate_and_calculate_timing(
            target_duration_seconds=req.target_duration_seconds,
            blocks=blocks_dicts,
            hook_variants=req.hook_variants
        )

        # 3. Kiem dinh tuyen bo san pham (Fact-Check - T090, T091, P09-09)
        manual_claims_dicts = [c.model_dump() for c in (req.claims or [])]
        checked_claims = claim_checker.check_script_claims(
            db=db,
            brief_version_id=idea.brief_version_id,
            blocks=timing_info["timed_blocks"],
            hook_variants=req.hook_variants,
            manual_claims=manual_claims_dicts,
            title=req.title
        )

        blocking_count = sum(1 for c in checked_claims if c.get("verification_status") in ["BLOCKING", "NEEDS_FACT_CHECK"])
        
        # P09-05: Sai dung sai thoi luong khong duoc vao READY_FOR_REVIEW
        if blocking_count > 0:
            initial_status = "NEEDS_FACT_CHECK"
        elif not timing_info["duration_tolerance_passed"]:
            initial_status = "DRAFT"
        else:
            initial_status = "READY_FOR_REVIEW"

        # 4. Luu vao database (Version 1)
        script = ScriptDraftVersion(
            workspace_id=workspace_id,
            idea_id=idea.id,
            created_by_user_id=user_id,
            version=1,
            title=req.title,
            target_duration_seconds=req.target_duration_seconds,
            hook_variants_json=json.dumps(req.hook_variants),
            blocks_json=json.dumps(timing_info["timed_blocks"]),
            claims_json=json.dumps(checked_claims),
            status=initial_status
        )
        db.add(script)
        db.commit()
        db.refresh(script)

        # Ghi log audit event
        audit = AuditEvent(
            workspace_id=workspace_id,
            actor_id=user_id,
            event_type="SCRIPT_CREATE",
            details=json.dumps({
                "script_id": script.id,
                "idea_id": idea.id,
                "version": 1,
                "blocking_claims_count": blocking_count
            })
        )
        db.add(audit)
        db.commit()

        return self._to_script_out(script)

    def approve_script(
        self,
        db: Session,
        workspace_id: str,
        user_id: str,
        script_id: str
    ) -> ScriptDraftOut:
        script = db.query(ScriptDraftVersion).filter(
            ScriptDraftVersion.id == script_id,
            ScriptDraftVersion.workspace_id == workspace_id
        ).first()

        if not script:
            raise HTTPException(status_code=404, detail="ScriptDraftVersion not found in workspace")

        # P09-05: Kiem tra dung sai thoi luong truoc khi phe duyet
        if not script.duration_tolerance_passed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error_code": "DURATION_OUT_OF_TOLERANCE",
                    "message": f"Kịch bản có thời lượng thực tế ({script.actual_duration_seconds}s) vượt dung sai cho phép so với mục tiêu ({script.target_duration_seconds}s)."
                }
            )

        # 1. Kiem tra tuyen bo can kiem dinh (T090, T091, P09-09)
        idea = db.query(IdeaCard).filter(IdeaCard.id == script.idea_id).first()
        if not idea:
            raise HTTPException(status_code=404, detail="Associated IdeaCard not found")

        # Quet lai toan bo claims de doi soat moi nhat
        checked_claims = claim_checker.check_script_claims(
            db=db,
            brief_version_id=idea.brief_version_id,
            blocks=script.blocks,
            hook_variants=script.hook_variants,
            manual_claims=script.claims,
            title=script.title
        )
        script.claims = checked_claims

        blocking_claims = [c for c in checked_claims if c.get("verification_status") in ["BLOCKING", "NEEDS_FACT_CHECK"]]
        if blocking_claims:
            # T090: Bat buoc chan phe duyet khi con tuyen bo BLOCKING
            blocking_reasons = "; ".join([f"'{c['claim_text']}': {c.get('notes', '')}" for c in blocking_claims[:3]])
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error_code": "CANNOT_APPROVE_UNVERIFIED_CLAIMS",
                    "message": f"Không thể duyệt kịch bản vì còn {len(blocking_claims)} tuyên bố chưa được kiểm định từ tài liệu hãng (AllowedFact): {blocking_reasons}"
                }
            )

        # T091: Tat ca tuyen bo hop le -> Phe duyet thanh cong
        script.status = "APPROVED"
        script.approved_by_user_id = user_id
        script.approved_at = utc_now()
        script.rejection_reason = None
        db.commit()
        db.refresh(script)

        # Audit event
        audit = AuditEvent(
            workspace_id=workspace_id,
            actor_id=user_id,
            event_type="SCRIPT_APPROVE",
            details=json.dumps({"script_id": script.id, "version": script.version})
        )
        db.add(audit)
        db.commit()

        return self._to_script_out(script)

    def edit_script(
        self,
        db: Session,
        workspace_id: str,
        user_id: str,
        script_id: str,
        req: ScriptDraftEditRequest
    ) -> ScriptDraftOut:
        script = db.query(ScriptDraftVersion).filter(
            ScriptDraftVersion.id == script_id,
            ScriptDraftVersion.workspace_id == workspace_id
        ).first()

        if not script:
            raise HTTPException(status_code=404, detail="ScriptDraftVersion not found in workspace")

        idea = db.query(IdeaCard).filter(IdeaCard.id == script.idea_id).first()
        if not idea:
            raise HTTPException(status_code=404, detail="IdeaCard not found")

        # P09-04: Neu kich ban da tung APPROVED hoac SUPERSEDED hoac da co approved_at:
        # BAT BUOC tao ban ghi moi bat bien dua tren version max + 1, khong sua de!
        if script.status in ("APPROVED", "SUPERSEDED") or script.approved_at is not None:
            if script.status == "APPROVED":
                script.status = "SUPERSEDED" # Chuyen phien ban cu thanh SUPERSEDED
                db.flush()

            # Tim max version theo idea_id de tranh va cham (P02-04 / P09-04)
            existing_vers = db.query(ScriptDraftVersion.version).filter(
                ScriptDraftVersion.idea_id == script.idea_id
            ).all()
            max_ver = max([v[0] for v in existing_vers]) if existing_vers else script.version
            new_version = max_ver + 1

            new_title = req.title if req.title is not None else script.title
            new_target_duration = req.target_duration_seconds if req.target_duration_seconds is not None else script.target_duration_seconds
            new_hooks = req.hook_variants if req.hook_variants is not None else script.hook_variants
            
            blocks_dicts = [b.model_dump() for b in req.blocks] if req.blocks is not None else script.blocks
            timing_info = timing_calculator.validate_and_calculate_timing(
                target_duration_seconds=new_target_duration,
                blocks=blocks_dicts,
                hook_variants=new_hooks
            )

            manual_claims = [c.model_dump() for c in req.claims] if req.claims is not None else script.claims
            checked_claims = claim_checker.check_script_claims(
                db=db,
                brief_version_id=idea.brief_version_id,
                blocks=timing_info["timed_blocks"],
                hook_variants=new_hooks,
                manual_claims=manual_claims,
                title=new_title
            )
            blocking_count = sum(1 for c in checked_claims if c.get("verification_status") in ["BLOCKING", "NEEDS_FACT_CHECK"])
            
            if blocking_count > 0:
                initial_status = "NEEDS_FACT_CHECK"
            elif not timing_info["duration_tolerance_passed"]:
                initial_status = "DRAFT"
            else:
                initial_status = "DRAFT"

            new_script = ScriptDraftVersion(
                workspace_id=workspace_id,
                idea_id=script.idea_id,
                created_by_user_id=user_id,
                version=new_version,
                title=new_title,
                target_duration_seconds=new_target_duration,
                hook_variants_json=json.dumps(new_hooks),
                blocks_json=json.dumps(timing_info["timed_blocks"]),
                claims_json=json.dumps(checked_claims),
                status=initial_status
            )
            db.add(new_script)
            db.commit()
            db.refresh(new_script)

            audit = AuditEvent(
                workspace_id=workspace_id,
                actor_id=user_id,
                event_type="SCRIPT_EDIT_IMMUTABLE_VERSION_CREATED",
                details=json.dumps({
                    "old_script_id": script.id,
                    "old_version": script.version,
                    "new_script_id": new_script.id,
                    "new_version": new_script.version
                })
            )
            db.add(audit)
            db.commit()

            return self._to_script_out(new_script)

        else:
            # Kich ban dang o trang thai nhap (chua tung duoc APPROVED) -> sua truc tiep
            if req.title is not None:
                script.title = req.title
            if req.target_duration_seconds is not None:
                script.target_duration_seconds = req.target_duration_seconds
            if req.hook_variants is not None:
                script.hook_variants = req.hook_variants

            if req.blocks is not None:
                blocks_dicts = [b.model_dump() for b in req.blocks]
                timing_info = timing_calculator.validate_and_calculate_timing(
                    target_duration_seconds=script.target_duration_seconds,
                    blocks=blocks_dicts,
                    hook_variants=script.hook_variants
                )
                script.blocks = timing_info["timed_blocks"]

            manual_claims = [c.model_dump() for c in req.claims] if req.claims is not None else script.claims
            checked_claims = claim_checker.check_script_claims(
                db=db,
                brief_version_id=idea.brief_version_id,
                blocks=script.blocks,
                hook_variants=script.hook_variants,
                manual_claims=manual_claims,
                title=script.title
            )
            script.claims = checked_claims

            blocking_count = sum(1 for c in checked_claims if c.get("verification_status") in ["BLOCKING", "NEEDS_FACT_CHECK"])
            if blocking_count > 0:
                script.status = "NEEDS_FACT_CHECK"
            elif not script.duration_tolerance_passed:
                script.status = "DRAFT"
            else:
                script.status = "READY_FOR_REVIEW"

            db.commit()
            db.refresh(script)
            return self._to_script_out(script)

    def reject_script(
        self,
        db: Session,
        workspace_id: str,
        user_id: str,
        script_id: str,
        req: ScriptReviewRequest
    ) -> ScriptDraftOut:
        script = db.query(ScriptDraftVersion).filter(
            ScriptDraftVersion.id == script_id,
            ScriptDraftVersion.workspace_id == workspace_id
        ).first()

        if not script:
            raise HTTPException(status_code=404, detail="ScriptDraftVersion not found in workspace")

        script.status = "REJECTED"
        script.rejection_reason = req.reviewer_notes or "Rejected by reviewer"
        db.commit()
        db.refresh(script)

        # Audit event
        audit = AuditEvent(
            workspace_id=workspace_id,
            actor_id=user_id,
            event_type="SCRIPT_REJECT",
            details=json.dumps({"script_id": script.id, "reason": script.rejection_reason})
        )
        db.add(audit)
        db.commit()

        return self._to_script_out(script)

    def list_scripts(
        self,
        db: Session,
        workspace_id: str,
        idea_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[ScriptDraftOut]:
        query = db.query(ScriptDraftVersion).filter(ScriptDraftVersion.workspace_id == workspace_id)
        if idea_id:
            query = query.filter(ScriptDraftVersion.idea_id == idea_id)
        if status:
            query = query.filter(ScriptDraftVersion.status == status)

        scripts = query.order_by(ScriptDraftVersion.created_at.desc()).limit(limit).all()
        return [self._to_script_out(s) for s in scripts]

    def get_script(
        self,
        db: Session,
        workspace_id: str,
        script_id: str
    ) -> ScriptDraftOut:
        script = db.query(ScriptDraftVersion).filter(
            ScriptDraftVersion.id == script_id,
            ScriptDraftVersion.workspace_id == workspace_id
        ).first()

        if not script:
            raise HTTPException(status_code=404, detail="ScriptDraftVersion not found")

        return self._to_script_out(script)

script_service = ScriptService()
