# Bo phat hien trung lap y tuong da duyet: DuplicateDetector (T085)
import re
from typing import Optional, Tuple, List
from sqlalchemy.orm import Session

from src.models.entities import IdeaCard

class DuplicateDetector:
    """
    Phat hien y tuong tuong dong hoac trung lap voi cac y tuong da duoc phe duyet (APPROVED).
    Khi do tuong dong >= threshold (mac dinh 70%), he thong gan co duplicate_warning.
    """

    def __init__(self, default_threshold: float = 0.70):
        self.default_threshold = default_threshold

    @staticmethod
    def _tokenize(text: str) -> set:
        if not text:
            return set()
        clean = text.lower()
        words = re.findall(r'\w+', clean)
        # Word unigrams
        tokens = set(words)
        # Word bigrams
        for i in range(len(words) - 1):
            tokens.add(f"{words[i]}_{words[i+1]}")
        # Char 3-grams for Vietnamese sub-word match
        for w in words:
            if len(w) >= 3:
                for j in range(len(w) - 2):
                    tokens.add(w[j:j+3])
        return tokens

    def calculate_similarity(self, text_a: str, text_b: str) -> float:
        set_a = self._tokenize(text_a)
        set_b = self._tokenize(text_b)
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a.intersection(set_b))
        union = len(set_a.union(set_b))
        if union == 0:
            return 0.0
        return round(float(intersection) / float(union), 4)

    def check_duplicate(
        self,
        db: Session,
        workspace_id: str,
        hook: str,
        content_angle: str,
        threshold: Optional[float] = None
    ) -> Tuple[bool, Optional[str], float, Optional[str]]:
        thresh = threshold or self.default_threshold
        target_text = f"{hook} {content_angle}".strip()

        # Lay tat ca cac y tuong da duyet trong workspace
        approved_cards: List[IdeaCard] = db.query(IdeaCard).filter(
            IdeaCard.workspace_id == workspace_id,
            IdeaCard.status == "APPROVED"
        ).all()

        max_sim = 0.0
        matched_card = None

        for card in approved_cards:
            existing_text = f"{card.hook} {card.content_angle}".strip()
            sim = self.calculate_similarity(target_text, existing_text)
            if sim > max_sim:
                max_sim = sim
                matched_card = card

        if max_sim >= thresh and matched_card:
            sim_pct = round(max_sim * 100, 1)
            warning = (
                f"Cảnh báo trùng lặp: Ý tưởng có độ tương đồng {sim_pct}% "
                f"với ý tưởng đã duyệt '{matched_card.title}' (ID: {matched_card.id})."
            )
            return True, warning, max_sim, matched_card.id

        return False, None, max_sim, None

duplicate_detector = DuplicateDetector()
