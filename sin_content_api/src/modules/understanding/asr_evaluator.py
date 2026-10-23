# ASR Evaluator & Capability Status (P06 / T063)
# Bao cao trung thuc ve nang luc ASR tieng Viet: khong tu nhan da hoan thien neu chua co tap am thanh duoc cap phep.
# Tinh toan WER (Word Error Rate) va do chinh xac thuat ngu chuyen nganh khi co tap doi chieu.

from typing import List, Dict, Any, Optional

def calculate_levenshtein_distance(seq1: List[str], seq2: List[str]) -> int:
    """Tinh khoang cach Levenshtein giua 2 danh sach tu."""
    m, n = len(seq1), len(seq2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if seq1[i - 1].lower() == seq2[j - 1].lower():
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])

    return dp[m][n]

def calculate_wer(reference: str, hypothesis: str) -> float:
    """Tinh Word Error Rate (WER) giua van ban tham chieu va van ban ASR nhan dang."""
    ref_words = reference.strip().split()
    hyp_words = hypothesis.strip().split()

    if not ref_words:
        return 0.0 if not hyp_words else 1.0

    edit_dist = calculate_levenshtein_distance(ref_words, hyp_words)
    return round(float(edit_dist) / float(len(ref_words)), 4)

class AsrEvaluator:
    _latest_evaluation: Optional[Dict[str, Any]] = None

    @classmethod
    def get_asr_capability_status(cls, licensed_audio_count: int = 0) -> Dict[str, Any]:
        """
        Bao cao trung thuc ve tinh trang ASR (T063 / P06-01):
        Neu chua co am thanh tieng Viet duoc cap phep ban quyen hoac chua chay danh gia tren tap doi chieu -> UNVERIFIED.
        Tuyet doi khong tra so lieu WER/accuracy bi dat/gan san.
        """
        if licensed_audio_count <= 0 or cls._latest_evaluation is None:
            return {
                "status": "UNVERIFIED",
                "offline_stub": True,
                "licensed_audio_count": max(0, licensed_audio_count),
                "wer_percentage": None,
                "terminology_accuracy": None,
                "message": (
                    "ASR status is UNVERIFIED: Requires customer-licensed Vietnamese audio "
                    "corpus with verified ground-truth transcripts. Do not claim verified "
                    "Vietnamese ASR without licensed audio proof and benchmark evaluation."
                )
            }
        else:
            eval_data = cls._latest_evaluation
            return {
                "status": "VERIFIED",
                "offline_stub": False,
                "licensed_audio_count": licensed_audio_count,
                "wer_percentage": eval_data.get("wer_percentage"),
                "terminology_accuracy": eval_data.get("domain_terminology_accuracy"),
                "message": f"ASR capability verified on {licensed_audio_count} licensed Vietnamese audio clips."
            }

    @classmethod
    def evaluate_transcripts(
        cls,
        references: List[str],
        hypotheses: List[str],
        domain_terms: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Danh gia do chinh xac cua ban ASR tren tap mau cap phep.
        Do luong WER trung binh va ty le nhan dien dung thuat ngu chuyen nganh.
        """
        if not references or not hypotheses or len(references) != len(hypotheses):
            raise ValueError("Danh sách tham chiếu và nhận dạng phải có cùng kích thước và không được rỗng.")

        wer_list = []
        for ref, hyp in zip(references, hypotheses):
            wer_list.append(calculate_wer(ref, hyp))

        avg_wer = round(sum(wer_list) / len(wer_list), 4)

        # Danh gia do chinh xac thuat ngu chuyen nganh (Domain terminology accuracy)
        term_acc = 1.0
        if domain_terms:
            total_term_instances = 0
            correct_term_instances = 0
            for ref, hyp in zip(references, hypotheses):
                ref_lower = ref.lower()
                hyp_lower = hyp.lower()
                for term in domain_terms:
                    t = term.lower()
                    if t in ref_lower:
                        total_term_instances += 1
                        if t in hyp_lower:
                            correct_term_instances += 1

            if total_term_instances > 0:
                term_acc = round(correct_term_instances / total_term_instances, 4)

        res = {
            "status": "EVALUATED",
            "wer_percentage": round(avg_wer * 100, 2),
            "domain_terminology_accuracy": round(term_acc * 100, 2),
            "total_evaluated_samples": len(references),
            "details": {
                "sample_wers": wer_list,
                "domain_terms_checked": domain_terms or []
            }
        }
        cls._latest_evaluation = res
        return res
