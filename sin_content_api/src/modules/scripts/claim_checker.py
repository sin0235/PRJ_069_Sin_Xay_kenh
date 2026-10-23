# Bo kiem dinh tuyen bo san pham doc lap: ClaimChecker (T090, T091)
# Nang cap giai quyet triet de cac loi P09-01, P09-02, P09-03, P09-09
import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from src.models.entities import AllowedFact, BrandBriefVersion

class ClaimChecker:
    """
    Bo kiem dinh tuyen bo san pham (Fact-Check Engine):
    - Quet toan bo tieu de (title), loi thoai (narration), mo ta canh (visual_cue) va hook_variants
      de phat hien cac tuyen bo dinh luong ve tinh nang, thoi gian, ty le phan tram, cong dung.
    - Doi soat 1:1 voi danh muc su that da duoc duyet (AllowedFact.status in ['APPROVED', 'VERIFIED']) cua thuong hieu.
    - Tuyen bo khong co trong AllowedFact bat buoc bi gan nhan BLOCKING / NEEDS_FACT_CHECK.
    - Chan tuyet doi khong cho phep phe duyet kich ban chua tuyen bo BLOCKING (T090).
    """

    QUANTITATIVE_PATTERNS = [
        (r"\b\d+(?:\.\d+)?\s*%", "Tỷ lệ phần trăm"),
        (r"\b\d+\s*(?:tiếng|giờ|ngày|phút|tuần|tháng|năm|hours?|days?|minutes?|seconds?|weeks?|months?|years?)\b", "Thời lượng / Thời gian"),
        (r"\b\d+\s*(?:triệu|tỷ|nghìn|k|đ|vnd|usd|dollars?)\b", "Định lượng tiền tệ"),
        (r"\b(?:inox\s*304|inox\s*316|gioăng\s*silicon|silicon|bpa\s*free|titanium)\b", "Chất liệu kỹ thuật"),
        (r"\b(?:trị\s*dứt\s*điểm|khỏi\s*hoàn\s*toàn|cam\s*kết\s*100%|chống\s*cháy\s*nổ|chữa\s*khỏi|chữa\s*bệnh|saves?\s*\d+)\b", "Cam kết tuyệt đối / Y tế")
    ]

    DISALLOWED_UNSUPPORTED_EXPANSIONS = [
        "chữa khỏi", "ung thư", "bệnh tật", "trị bệnh", "hoàn tiền", "chống cháy nổ", "100% khỏi", "cam kết 100%"
    ]

    def _normalize_text(self, text: str) -> str:
        return re.sub(r'\s+', ' ', text.lower().strip())

    def _extract_core_terms(self, text: str) -> List[str]:
        norm = self._normalize_text(text)
        terms = []
        # Thoi gian
        time_matches = re.findall(r'\b\d+\s*(?:tiếng|giờ|ngày|phút|hours?|days?)\b', norm)
        terms.extend(time_matches)
        # Phan tram
        pct_matches = re.findall(r'\b\d+(?:\.\d+)?\s*%\b', norm)
        terms.extend(pct_matches)
        # Chat lieu
        if "inox 304" in norm or "inox304" in norm:
            terms.append("inox 304")
        if "gioăng silicon" in norm or "silicon" in norm:
            terms.append("silicon")
        if "100%" in norm:
            terms.append("100%")
        return terms

    def _match_with_allowed_facts(
        self,
        claim_str: str,
        facts: List[AllowedFact]
    ) -> Optional[AllowedFact]:
        norm_claim = self._normalize_text(claim_str)
        claim_terms = self._extract_core_terms(norm_claim)

        # P09-01: Neu claim co phat bieu mo rong cong dung y te/tuyet doi ma fact khong co thi khong cho match!
        claim_has_unsupported_expansion = any(exp in norm_claim for exp in self.DISALLOWED_UNSUPPORTED_EXPANSIONS)

        for fact in facts:
            norm_fact = self._normalize_text(fact.claim_text)
            fact_has_expansion = any(exp in norm_fact for exp in self.DISALLOWED_UNSUPPORTED_EXPANSIONS)

            # Neu claim tuyen bo cong dung mo rong ma fact khong he co -> tu choi match
            if claim_has_unsupported_expansion and not fact_has_expansion:
                continue
            
            # 1. So khop chua nhau
            if norm_claim in norm_fact or norm_fact in norm_claim:
                return fact
                
            # 2. So khop tu khoa dinh luong cot loi
            fact_terms = self._extract_core_terms(norm_fact)
            if claim_terms and fact_terms:
                # Kiem tra mau thuan thoi gian (vi du: 24 tieng vs 6 tieng)
                time_in_claim = re.findall(r'\b\d+\s*(?:tiếng|giờ)\b', norm_claim)
                time_in_fact = re.findall(r'\b\d+\s*(?:tiếng|giờ)\b', norm_fact)
                if time_in_claim:
                    if not time_in_fact:
                        continue
                    if not any(tc in time_in_fact for tc in time_in_claim):
                        continue # Lech thoi gian dinh luong -> khong cho match!

                # Kiem tra mau thuan phan tram (vi du: 100% vs 50%)
                pct_in_claim = re.findall(r'\b\d+(?:\.\d+)?\s*%\b', norm_claim)
                pct_in_fact = re.findall(r'\b\d+(?:\.\d+)?\s*%\b', norm_fact)
                if pct_in_claim and not pct_in_fact:
                    continue # Claim co phan tram ma fact khong co -> tu choi!
                if pct_in_claim and pct_in_fact:
                    if not any(pc in pct_in_fact for pc in pct_in_claim):
                        continue

                # Neu co it nhat 1 tu khoa cot loi khop nhau va khong co phat bieu them cong dung sai lech
                if any(ct in fact_terms for ct in claim_terms):
                    return fact

        return None

    def check_script_claims(
        self,
        db: Session,
        brief_version_id: str,
        blocks: List[Dict[str, Any]],
        hook_variants: List[str],
        manual_claims: Optional[List[Dict[str, Any]]] = None,
        title: str = ""
    ) -> List[Dict[str, Any]]:
        # 1. P09-02: CHI LAY AllowedFact o trang thai APPROVED hoac VERIFIED (loai bo PENDING, UNVERIFIED, REJECTED)
        allowed_facts: List[AllowedFact] = db.query(AllowedFact).filter(
            AllowedFact.brief_version_id == brief_version_id,
            AllowedFact.verification_status.in_(["APPROVED", "VERIFIED"])
        ).all()

        checked_claims = []
        seen_claim_texts = set()

        # 2. Xu ly cac manual claims duoc truyen len (neu co)
        if manual_claims:
            for mc in manual_claims:
                text = mc.get("claim_text", "").strip()
                if not text or text in seen_claim_texts:
                    continue
                seen_claim_texts.add(text)

                matched_fact = self._match_with_allowed_facts(text, allowed_facts)
                if matched_fact:
                    checked_claims.append({
                        "claim_text": text,
                        "claim_type": mc.get("claim_type", "QUANTITATIVE"),
                        "allowed_fact_id": matched_fact.id,
                        "source_citation": matched_fact.source_citation,
                        "verification_status": "VERIFIED",
                        "notes": f"Khớp với tài liệu kỹ thuật đã duyệt: '{matched_fact.claim_text}'"
                    })
                else:
                    checked_claims.append({
                        "claim_text": text,
                        "claim_type": mc.get("claim_type", "QUANTITATIVE"),
                        "allowed_fact_id": None,
                        "source_citation": None,
                        "verification_status": "BLOCKING",
                        "notes": f"Tuyên bố định lượng '{text}' không có nguồn chứng minh từ tài liệu hãng đã duyệt (AllowedFact APPROVED/VERIFIED)."
                    })

        # 3. P09-09: Quet toan bo title, narration, visual cues va hook variants
        all_text_snippets = []
        if title:
            all_text_snippets.append(title)
        for h in hook_variants:
            all_text_snippets.append(h)
        for b in blocks:
            if b.get("narration"):
                all_text_snippets.append(b["narration"])
            if b.get("visual_cue"):
                all_text_snippets.append(b["visual_cue"])

        full_content = "\n".join(all_text_snippets)

        # Tach thanh cac cau/menh de rieng biet
        sentences = [s.strip() for s in re.split(r'[\n.!?]+', full_content) if s.strip()]

        for sentence in sentences:
            has_pattern = False
            detected_desc = ""
            for pattern, desc in self.QUANTITATIVE_PATTERNS:
                if re.search(pattern, sentence, re.IGNORECASE):
                    has_pattern = True
                    detected_desc = desc
                    break

            if has_pattern:
                norm_s = self._normalize_text(sentence)
                if norm_s in seen_claim_texts:
                    continue
                seen_claim_texts.add(norm_s)

                matched_fact = self._match_with_allowed_facts(sentence, allowed_facts)
                if matched_fact:
                    checked_claims.append({
                        "claim_text": sentence,
                        "claim_type": "QUANTITATIVE",
                        "allowed_fact_id": matched_fact.id,
                        "source_citation": matched_fact.source_citation,
                        "verification_status": "VERIFIED",
                        "notes": f"Khớp với AllowedFact đã duyệt: '{matched_fact.claim_text}'"
                    })
                else:
                    checked_claims.append({
                        "claim_text": sentence,
                        "claim_type": "QUANTITATIVE",
                        "allowed_fact_id": None,
                        "source_citation": None,
                        "verification_status": "BLOCKING",
                        "notes": f"Tuyên bố '{sentence}' ({detected_desc}) thiếu tài liệu kỹ thuật chứng minh đã duyệt. Cần xác thực trước khi duyệt."
                    })

        return checked_claims

claim_checker = ClaimChecker()
