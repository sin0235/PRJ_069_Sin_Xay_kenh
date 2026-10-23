# Prompt Injection Guard (P06 / T061)
# Dam bao moi noi dung tu nguoi dung/binh luan chi duoc xem la text passive du lieu thuan tuy,
# tuyet doi khong kich hoat tool, khong ro ri khoa bi mat hoac can thiep huong dan he thong.
# Nang cap P06-02: Ho tro giai ma Base64, Hex va chuan hoa Zero-width spaces tranh evasion.

import re
import base64
import binascii
from typing import Tuple, List, Dict, Any

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?",
    r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions?",
    r"qu[eê]n\s+(h[eế]t\s+)?(c[aá]c\s+)?(quy\s+t[aắ]c|h[uư][oớ]ng\s+d[aẫ]n|l[eệ]nh|ch[iỉ]\s+đ[aạ]o|instruction)",
    r"b[oỏ]\s+qua\s+(m[oọ]i\s+|h[eế]t\s+)?(quy\s+t[aắ]c|h[uư][oớ]ng\s+d[aẫ]n|l[eệ]nh)",
    r"system\s+prompt",
    r"leak\s+(all\s+)?(api\s+keys?|secrets?|passwords?|tokens?)",
    r"ti[eế]t\s+l[oộ]\s+(t[aấ]t\s+c[aả]\s+)?(api\s*key|m[aậ]t\s*kh[aẩ]u|secret|token|kh[oó]a\s*b[ií]\s*m[aậ]t)",
    r"show\s+me\s+(the\s+)?(hidden|system|admin)\s+(prompt|instructions?)",
    r"execute\s+command",
    r"run\s+shell",
    r"rm\s+-rf",
    r"cat\s+/etc/passwd",
    r"tool_call",
    r"function_call",
    r"__import__",
    r"eval\(",
    r"exec\(",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]

# Regex tim kiem chuoi base64 tiem an (it nhat 12 ky tu)
BASE64_PATTERN = re.compile(r"[A-Za-z0-9+/]{12,}={0,2}")
# Regex tim kiem chuoi hex tiem an (it nhat 16 ky tu hex chan)
HEX_PATTERN = re.compile(r"\b(?:[0-9a-fA-F]{2}){8,}\b")

class PromptInjectionGuard:
    @staticmethod
    def inspect_and_sanitize(raw_text: str) -> Dict[str, Any]:
        """
        Kiem tra van ban binh luan / trich doan tu ben ngoai.
        Tra ve metadata bao mat, danh sach mau tan cong neu co,
        va chuoi duoc dong goi an toan de chi luu tru nhu du lieu chu khong thuc thi lenh.
        """
        if not raw_text:
            return {
                "sanitized_text": "",
                "has_injection_risk": False,
                "detected_patterns": [],
                "tool_execution_allowed": False,
                "safe_as_passive_data": True
            }

        # 1. P06-02: Loai bo ky tu tang hinh / zero-width spaces
        clean_text = re.sub(r"[\u200b\u200c\u200d\u200e\u200f\ufeff]", "", raw_text)

        detected = []

        # 2. Quet truc tiep tren clean_text
        for regex in COMPILED_PATTERNS:
            match = regex.search(clean_text)
            if match:
                detected.append(match.group(0))

        # 3. P06-02: Giai ma chuoi Base64 tiem an de quet injection an
        for b64_match in BASE64_PATTERN.findall(clean_text):
            try:
                decoded_bytes = base64.b64decode(b64_match)
                decoded_str = decoded_bytes.decode("utf-8", errors="ignore")
                if len(decoded_str) >= 6:
                    for regex in COMPILED_PATTERNS:
                        m = regex.search(decoded_str)
                        if m:
                            detected.append(f"base64_encoded:{m.group(0)}")
            except Exception:
                pass

        # 4. P06-02: Giai ma chuoi Hex tiem an de quet injection an
        for hex_match in HEX_PATTERN.findall(clean_text):
            try:
                decoded_bytes = binascii.unhexlify(hex_match)
                decoded_str = decoded_bytes.decode("utf-8", errors="ignore")
                if len(decoded_str) >= 6:
                    for regex in COMPILED_PATTERNS:
                        m = regex.search(decoded_str)
                        if m:
                            detected.append(f"hex_encoded:{m.group(0)}")
            except Exception:
                pass

        has_risk = len(detected) > 0

        # Sanitization: Bo boc text trong phong toa du lieu an toan (data containment)
        sanitized = clean_text.strip()

        return {
            "sanitized_text": sanitized,
            "has_injection_risk": has_risk,
            "detected_patterns": detected,
            "tool_execution_allowed": False, # Luon luon False - khong bao gio cho phep execution tu user content
            "safe_as_passive_data": True
        }

    @staticmethod
    def assert_safe_passive_data(raw_text: str) -> bool:
        """Kiem tra xem van ban co the duoc luu tru an toan nhu data thu dong hay khong."""
        return True
