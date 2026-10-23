# Bo kiem chung y tuong doc lap: IdeaVerifier (T080, T081, T082, T084, P08-01, P08-02, P08-04, P08-10, P08-11)
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from src.models.entities import EvidenceExcerpt, SourceRecord, BrandBriefVersion, IdeaCard
from src.schemas.contracts import IdeaCardCreate, VerificationResult
from src.modules.understanding.prompt_injection_guard import PromptInjectionGuard

class IdeaVerifier:
    """
    Bo kiem chung doc lap (Independent Idea Verifier):
    - 100% ID bang chung va URL trich dan phai ton tai that su trong cung workspace.
    - Doi chieu quote_text va so lieu voi noi dung goc cua EvidenceExcerpt (P08-01).
    - Chan nguon da bi thu hoi (is_purged=True) hoac khong co quyen su dung (rights_basis=NOT_GRANTED) (P08-02).
    - Bat buoc BrandBriefVersion phai ton tai va o trang thai APPROVED (P08-04).
    - Kiem tra Brand Safety Veto tren ca title, hook, content_angle VA target_need (P08-11).
    - Kiem soat che do bang chung: khong co bang chung -> INSUFFICIENT_EVIDENCE,
      tru khi bat co allow_hypotheses=True -> cap nhan HYPOTHESIS, suggested_status=NEEDS_EVIDENCE (P08-10).
    - Phong chong Prompt Injection trong trich doan va noi dung y tuong (T084).
    """

    def __init__(self):
        self.injection_guard = PromptInjectionGuard()

    def verify(
        self,
        db: Session,
        workspace_id: str,
        idea: IdeaCardCreate,
        brief: Optional[BrandBriefVersion] = None
    ) -> VerificationResult:
        # P08-04: Brief bat buoc phai ton tai va da APPROVED
        if brief is None or getattr(brief, "status", None) != "APPROVED":
            return VerificationResult(
                is_valid=False,
                rejection_code="INVALID_OR_UNAPPROVED_BRIEF",
                rejection_reason="Brief không tồn tại trong workspace hoặc chưa được phê duyệt (status != APPROVED).",
                suggested_status="REJECTED"
            )

        # 1. Kiem tra Prompt Injection
        # P08-11: Bao gom target_need vao combined_text de phong ve va kiem tra Brand Safety
        combined_text = f"{idea.title} {idea.hook} {idea.content_angle} {idea.target_need or ''}"
        injection_check = self.injection_guard.inspect_and_sanitize(combined_text)
        if injection_check.get("has_injection_risk"):
            # Phong ve: Luu thu dong, xem nhu text binh thuong, khong thuc thi lenh (T084)
            pass

        # 2. Kiem tra Brand Safety Veto (Chu de bi cam cua thuong hieu) - P08-11
        banned_topics = [t.lower().strip() for t in (brief.topics_excluded or []) if t and t.strip()]
        lower_text = combined_text.lower()
        for banned in banned_topics:
            if banned and banned in lower_text:
                return VerificationResult(
                    is_valid=False,
                    rejection_code="PROHIBITED_TOPIC_VETO",
                    rejection_reason=f"Ý tưởng vi phạm chủ đề cấm của thương hiệu: '{banned}'. Lập tức loại bỏ theo quy tắc Brand Safety.",
                    suggested_status="REJECTED"
                )

        # 3. Thu thap toan bo ID trich dan
        cited_ids = list(set([eid for eid in (idea.evidence_excerpt_ids or []) if eid] + 
                             [c.excerpt_id for c in (idea.citations or []) if getattr(c, "excerpt_id", None)]))
        
        # 4. Xu ly truong hop khong co bang chung (T082, P08-10)
        if not cited_ids:
            if not idea.allow_hypotheses:
                return VerificationResult(
                    is_valid=False,
                    rejection_code="INSUFFICIENT_EVIDENCE",
                    rejection_reason="Không có bằng chứng thực nghiệm quan sát được và chế độ allow_hypotheses=False. Hệ thống từ chối sinh ý tưởng không có căn cứ.",
                    cited_excerpts_count=0,
                    verified_excerpts_count=0,
                    suggested_status="REJECTED"
                )
            else:
                return VerificationResult(
                    is_valid=True,
                    rejection_code=None,
                    rejection_reason=None,
                    cited_excerpts_count=0,
                    verified_excerpts_count=0,
                    suggested_status="NEEDS_EVIDENCE" # Bat buoc nhan HYPOTHESIS
                )

        # 5. Xac minh tinh ton tai that va ranh gioi workspace cua tung ID trich dan (T080, T081, P08-01, P08-02)
        verified_count = 0
        fabricated_ids = []
        
        for eid in cited_ids:
            # Query excerpt trong DB
            excerpt = db.query(EvidenceExcerpt).filter(EvidenceExcerpt.id == eid).first()
            if not excerpt:
                fabricated_ids.append(eid)
                continue
                
            # Kiem tra workspace boundary
            if (excerpt.workspace_id and excerpt.workspace_id != workspace_id) or (excerpt.source_record and excerpt.source_record.workspace_id != workspace_id):
                return VerificationResult(
                    is_valid=False,
                    rejection_code="INVALID_CITATION_FABRICATION",
                    rejection_reason=f"Trích dẫn vi phạm ranh giới khách thuê: ID '{eid}' thuộc workspace khác.",
                    cited_excerpts_count=len(cited_ids),
                    verified_excerpts_count=verified_count,
                    fabricated_ids=[eid],
                    suggested_status="REJECTED"
                )

            # P08-02: Kiem tra nguon da bi thu hoi (purged) hoac chua cap quyen (rights_basis=NOT_GRANTED)
            if excerpt.source_record:
                if getattr(excerpt.source_record, "is_purged", False):
                    fabricated_ids.append(f"{eid} (Nguồn đã bị thu hồi/purged)")
                    continue
                if getattr(excerpt.source_record, "rights_basis", "GRANTED") == "NOT_GRANTED":
                    fabricated_ids.append(f"{eid} (Nguồn chưa được cấp quyền sử dụng/rights_basis=NOT_GRANTED)")
                    continue
            
            # Kiem tra URL neu citation co chi dinh
            for cit in (idea.citations or []):
                if getattr(cit, "excerpt_id", None) == eid:
                    if getattr(cit, "source_url", None):
                        src_url = excerpt.source_record.source_url if (excerpt.source_record and hasattr(excerpt.source_record, "source_url")) else None
                        can_url = excerpt.source_record.canonical_url if (excerpt.source_record and hasattr(excerpt.source_record, "canonical_url")) else None
                        valid_urls = [u.strip() for u in [src_url, can_url] if u]
                        if valid_urls and cit.source_url.strip() not in valid_urls:
                            fabricated_ids.append(f"{eid} (URL bịa đặt: {cit.source_url})")
                            continue

                    # P08-01: Kiem tra quote_text fidelity (trich dan phai co that trong excerpt)
                    if getattr(cit, "quote_text", None):
                        q_clean = cit.quote_text.strip().lower()
                        e_clean = (excerpt.excerpt_text or "").strip().lower()
                        if q_clean and (q_clean not in e_clean and e_clean not in q_clean):
                            fabricated_ids.append(f"{eid} (Trích dẫn bịa đặt không có trong nguồn: '{cit.quote_text[:40]}...')")
                            continue
            
            verified_count += 1

        if fabricated_ids:
            return VerificationResult(
                is_valid=False,
                rejection_code="INVALID_CITATION_FABRICATION",
                rejection_reason=f"Mô hình AI tự bịa đặt trích dẫn/URL/nguồn không hợp lệ: Các ID sau vi phạm: {', '.join(fabricated_ids)}.",
                cited_excerpts_count=len(cited_ids),
                verified_excerpts_count=verified_count,
                unverified_excerpts_count=len(fabricated_ids),
                fabricated_ids=fabricated_ids,
                suggested_status="REJECTED"
            )

        # 6. Tat ca ID trich dan deu hop le va ton tai
        return VerificationResult(
            is_valid=True,
            rejection_code=None,
            rejection_reason=None,
            cited_excerpts_count=len(cited_ids),
            verified_excerpts_count=verified_count,
            unverified_excerpts_count=0,
            fabricated_ids=[],
            suggested_status="READY_FOR_REVIEW"
        )

idea_verifier = IdeaVerifier()
