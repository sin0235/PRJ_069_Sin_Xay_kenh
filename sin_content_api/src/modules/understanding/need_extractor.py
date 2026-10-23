# Need Extractor (P06 / T060, T062)
# Boc tach tin hieu nhu cau, bao toan trich dan goc (quote), phan biet OBSERVED_DIRECT va INFERRED_UNVERIFIED,
# va kiem soat chat che cac tuyen bo nhan khau hoc khong co so lieu phan tich chinh chu (P06-02, P06-05).

import re
import json
from typing import List, Dict, Any, Optional

# Taxonomy rules va Synsets cho Tieng Viet
NEED_PATTERNS = [
    {
        "intent_group": "OBJECTIONS",
        "need_category": "PACKAGING_LEAKAGE",
        "label": "Nguy cơ rò rỉ / tràn nước canh (Packaging Leakage Risk)",
        "keywords": [
            r"tràn\s+canh",
            r"rò\s+rỉ\s+nắp",
            r"đổ\s+nước\s+canh",
            r"chảy\s+nước",
            r"bung\s+nắp",
            r"hở\s+nắp",
            r"nắp\s+lỏng",
            r"ướt\s+(hết\s+)?(ba\s+lô|túi|tài\s+liệu)"
        ]
    },
    {
        "intent_group": "OBJECTIONS",
        "need_category": "PRICE_CONCERN",
        "label": "Quan ngại về giá thành cao (Price Resistance)",
        "keywords": [
            r"đắt\s+quá",
            r"giá\s+chát",
            r"giá\s+cao",
            r"không\s+đáng\s+tiền",
            r"hơi\s+mắc"
        ]
    },
    {
        "intent_group": "PROBLEMS",
        "need_category": "MATERIAL_SAFETY",
        "label": "Mùi nhựa và an toàn chất liệu (Material & Odor Safety)",
        "keywords": [
            r"mùi\s+nhựa",
            r"nhựa\s+hôi",
            r"nhựa\s+tái\s+chế",
            r"chất\s+liệu\s+kém"
        ]
    },
    {
        "intent_group": "QUESTIONS",
        "need_category": "MICROWAVE_SAFETY",
        "label": "Khả năng sử dụng trong lò vi sóng (Microwave Compatibility)",
        "keywords": [
            r"quay\s+lò\s+vi\s+sóng",
            r"lò\s+vi\s+sóng\s+được\s+không",
            r"chịu\s+nhiệt\s+bao\s+nhiêu",
            r"bỏ\s+lò\s+vi\s+sóng"
        ]
    },
    {
        "intent_group": "CONTEXTS",
        "need_category": "OFFICE_COMMUTE",
        "label": "Bối cảnh mang cơm đi làm văn phòng / xe máy (Office Commute)",
        "keywords": [
            r"mang\s+đi\s+làm",
            r"dân\s+văn\s+phòng",
            r"đi\s+xe\s+máy",
            r"để\s+cốp\s+xe",
            r"ổ\s+gà"
        ]
    }
]

# Patterns phat hien cac tuyen bo nhan khau hoc (Demographic Claims - T062 / P06-05)
DEMOGRAPHIC_PATTERNS = [
    r"(\d+[\.,]?\d*\s*(%|phần\s+trăm)\s*(người\s+xem|khán\s+giả|người\s+mua|khách\s+hàng|follow(er)?s?|dân\s+văn\s+phòng|phụ\s+nữ|nam\s+giới))",
    r"((khán\s+giả|người\s+xem|khách\s+hàng|người\s+dùng|follower)\s+(chủ\s+yếu|toàn\s+là|đa\s+phần|phần\s+lớn|đa\s+số|chiếm\s+đa\s+số)\s+(là\s+)?[^,\.\n]+)",
    r"((chủ\s+yếu|toàn\s+là|đa\s+phần|phần\s+lớn|đa\s+số)\s+là\s+(dân\s+văn\s+phòng|phụ\s+nữ|nam\s+giới|sinh\s+viên|giới\s+trẻ|người\s+lớn))",
    r"(độ\s+tuổi\s+(từ|chủ\s+yếu)\s+\d+\s*-\s*\d+)",
    r"((phụ\s+nữ|nam\s+giới|dân\s+văn\s+phòng|sinh\s+viên)\s+(độc\s+thân|ở|tại)\s+[^,\.\n]+)",
    r"(người\s+xem\s+đa\s+số\s+là\s+[^,\.\n]+)",
    r"(khán\s+giả\s+phần\s+lớn\s+là\s+[^,\.\n]+)"
]

class NeedExtractor:
    @staticmethod
    def detect_demographic_claims(text: str) -> List[str]:
        """Tim cac phat bieu ve nhan khau hoc khan gia trong text (P06-05)."""
        claims = []
        for pattern in DEMOGRAPHIC_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for m in matches:
                matched_str = m.group(0).strip()
                if matched_str and matched_str not in claims:
                    claims.append(matched_str)
        return claims

    @classmethod
    def is_demographic_statement(cls, text: str) -> bool:
        """Kiem tra xem doan text co chua phat bieu nhan khau hoc khong."""
        text_lower = text.lower()
        if cls.detect_demographic_claims(text):
            return True
        keywords_audience = ["người xem", "khán giả", "dân văn phòng", "phụ nữ", "nam giới", "độc thân"]
        keywords_quantifier = ["%", "phần trăm", "chủ yếu", "đa số", "phần lớn", "đa phần", "chiếm"]
        has_aud = any(k in text_lower for k in keywords_audience)
        has_quant = any(k in text_lower for k in keywords_quantifier)
        return has_aud and has_quant

    @classmethod
    def extract(
        cls,
        text: str,
        has_official_analytics: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Boc tach danh sach NeedSignal tu van ban.
        - Giu nguyen quote_text (trich doan goc).
        - Neu co phat bieu nhan khau hoc ma khong co bao cao chinh thuc (has_official_analytics=False):
          danh dau la INFERRED_UNVERIFIED va cap nhat demographic_inferences_json voi status UNSUPPORTED_INFERENCE.
        """
        signals = []
        demographic_claims = cls.detect_demographic_claims(text)
        has_any_demog = len(demographic_claims) > 0 or cls.is_demographic_statement(text)

        # 1. Kiem tra cac nhom nhu cau qua taxonomy
        for item in NEED_PATTERNS:
            matched_quotes = []
            for kw in item["keywords"]:
                pattern = re.compile(f"([^.!?\n]*{kw}[^.!?\n]*)", re.IGNORECASE)
                for match in pattern.finditer(text):
                    snippet = match.group(0).strip()
                    if snippet and snippet not in matched_quotes:
                        matched_quotes.append(snippet)

            if matched_quotes:
                for q in matched_quotes:
                    # Kiem tra xem trich doan co chua phat ngon nhan khau hoc khong
                    is_unsupported_demo = False
                    if not has_official_analytics and cls.is_demographic_statement(q):
                        is_unsupported_demo = True

                    if is_unsupported_demo:
                        obs_vs_inf = "INFERRED_UNVERIFIED"
                        conf = 0.3
                        demog_json = json.dumps([{
                            "claim": q,
                            "status": "UNSUPPORTED_INFERENCE",
                            "reason": "Demographic assertion lacks first-party verified TikTok Analytics report; cannot treat as ground truth"
                        }], ensure_ascii=False)
                    else:
                        obs_vs_inf = "OBSERVED_DIRECT"
                        conf = 0.95
                        demog_json = "[]"

                    signals.append({
                        "intent_group": item["intent_group"],
                        "need_category": item["need_category"],
                        "signal_text": f"{item['label']}: {q}",
                        "quote_text": q,
                        "observed_vs_inferred": obs_vs_inf,
                        "confidence_score": conf,
                        "demographic_inferences_json": demog_json
                    })

        # 2. Xu ly dac biet cho T062: Tuyen bo nhan khau hoc doc lap
        if demographic_claims:
            for claim in demographic_claims:
                # Kiem tra xem claim nay da duoc covers chua
                already_covered = any(claim.lower() in s["quote_text"].lower() for s in signals)
                if not already_covered:
                    if not has_official_analytics:
                        demog_records = [{
                            "claim": claim,
                            "status": "UNSUPPORTED_INFERENCE",
                            "reason": "Demographic assertion lacks first-party verified TikTok Analytics report; cannot treat as ground truth"
                        }]
                        signals.append({
                            "intent_group": "CONTEXTS",
                            "need_category": "DEMOGRAPHIC_UNVERIFIED",
                            "signal_text": f"Suy luận nhân khẩu học chưa kiểm chứng: {claim}",
                            "quote_text": claim,
                            "observed_vs_inferred": "INFERRED_UNVERIFIED",
                            "confidence_score": 0.3,
                            "demographic_inferences_json": json.dumps(demog_records, ensure_ascii=False)
                        })
                    else:
                        demog_records = [{
                            "claim": claim,
                            "status": "VERIFIED_BY_ANALYTICS",
                            "reason": "Backed by official first-party analytics report"
                        }]
                        signals.append({
                            "intent_group": "CONTEXTS",
                            "need_category": "DEMOGRAPHIC_VERIFIED",
                            "signal_text": f"Nhân khẩu học được kiểm chứng từ Analytics: {claim}",
                            "quote_text": claim,
                            "observed_vs_inferred": "OBSERVED_DIRECT",
                            "confidence_score": 0.95,
                            "demographic_inferences_json": json.dumps(demog_records, ensure_ascii=False)
                        })

        # Neu khong khop pattern cu the nhung van co noi dung, sinh tin hieu tong quan (P06-05 fallback guard)
        if not signals and len(text.strip()) > 5:
            if has_any_demog and not has_official_analytics:
                demog_records = [{
                    "claim": text.strip(),
                    "status": "UNSUPPORTED_INFERENCE",
                    "reason": "Demographic assertion lacks first-party verified TikTok Analytics report; cannot treat as ground truth"
                }]
                signals.append({
                    "intent_group": "CONTEXTS",
                    "need_category": "DEMOGRAPHIC_UNVERIFIED",
                    "signal_text": f"Suy luận nhân khẩu học chưa kiểm chứng: {text.strip()[:120]}",
                    "quote_text": text.strip(),
                    "observed_vs_inferred": "INFERRED_UNVERIFIED",
                    "confidence_score": 0.3,
                    "demographic_inferences_json": json.dumps(demog_records, ensure_ascii=False)
                })
            else:
                signals.append({
                    "intent_group": "PROBLEMS",
                    "need_category": "GENERAL_FEEDBACK",
                    "signal_text": f"Phản hồi từ người xem: {text.strip()[:120]}",
                    "quote_text": text.strip(),
                    "observed_vs_inferred": "OBSERVED_DIRECT",
                    "confidence_score": 0.7,
                    "demographic_inferences_json": "[]"
                })

        return signals
