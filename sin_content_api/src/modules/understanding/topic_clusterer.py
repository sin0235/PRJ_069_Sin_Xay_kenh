# Topic Clusterer (P06 / T060)
# Gom cum chu de va cac bien the tieng Viet cua cung mot su phan doi / nhu cau ve chung mot nhom.
# Module co the bat/tat an toan (toggleable).
# Bao toan 100% lien ket toi trich dan goc (quote_text) va EvidenceExcerpt.

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from src.models.entities import NeedSignal, TopicCluster, TopicClusterSignal

# Danh muc nhan cum chuan hoa
CLUSTER_LABELS = {
    ("OBJECTIONS", "PACKAGING_LEAKAGE"): "Nguy cơ rò rỉ & tràn nước canh khi di chuyển (Packaging Leakage Risk)",
    ("OBJECTIONS", "PRICE_CONCERN"): "Quan ngại mức giá và chi phí mua sắm (Price Barrier)",
    ("PROBLEMS", "MATERIAL_SAFETY"): "Chất lượng vật liệu và mùi nhựa khó chịu (Material Safety)",
    ("QUESTIONS", "MICROWAVE_SAFETY"): "Khả năng quay lò vi sóng và chịu nhiệt (Microwave Compatibility)",
    ("CONTEXTS", "OFFICE_COMMUTE"): "Bối cảnh mang cơm đi làm văn phòng bằng xe máy (Office Commute Context)",
    ("CONTEXTS", "DEMOGRAPHIC_UNVERIFIED"): "Tuyên bố nhân khẩu học chưa có kiểm chứng Analytics",
    ("CONTEXTS", "DEMOGRAPHIC_VERIFIED"): "Nhân khẩu học được xác nhận qua Analytics"
}

class TopicClusterer:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def cluster_workspace_signals(
        self,
        db: Session,
        workspace_id: str,
        intent_group_filter: Optional[str] = None
    ) -> List[TopicCluster]:
        """
        Quet cac NeedSignal trong workspace va gom cum theo intent_group & need_category.
        Tao TopicCluster va TopicClusterSignal de giu lien ket bat bien.
        """
        if not self.enabled:
            return []

        # Truy van tin hieu nhu cau chua duoc gom cum hoac toan bo tin hieu trong workspace
        query = db.query(NeedSignal).filter(NeedSignal.workspace_id == workspace_id)
        if intent_group_filter:
            query = query.filter(NeedSignal.intent_group == intent_group_filter)
        
        all_signals = query.all()
        if not all_signals:
            return []

        # Gom nhom theo (intent_group, need_category)
        groups: Dict[tuple, List[NeedSignal]] = {}
        for sig in all_signals:
            key = (sig.intent_group, sig.need_category)
            if key not in groups:
                groups[key] = []
            groups[key].append(sig)

        created_or_updated_clusters = []

        for (intent_grp, need_cat), sigs in groups.items():
            # Tim cluster da co trong workspace
            cluster = db.query(TopicCluster).filter(
                TopicCluster.workspace_id == workspace_id,
                TopicCluster.intent_group == intent_grp,
                TopicCluster.need_category == need_cat
            ).first()

            label = CLUSTER_LABELS.get(
                (intent_grp, need_cat),
                f"Cụm chủ đề: {need_cat} ({intent_grp})"
            )

            if not cluster:
                cluster = TopicCluster(
                    workspace_id=workspace_id,
                    cluster_label=label,
                    intent_group=intent_grp,
                    need_category=need_cat,
                    signal_count=len(sigs)
                )
                db.add(cluster)
                db.flush() # de co cluster.id
            else:
                cluster.signal_count = len(sigs)

            # Cap nhat lien ket TopicClusterSignal
            existing_links = {
                link.need_signal_id for link in db.query(TopicClusterSignal).filter(
                    TopicClusterSignal.cluster_id == cluster.id
                ).all()
            }

            for sig in sigs:
                if sig.id not in existing_links:
                    new_link = TopicClusterSignal(
                        cluster_id=cluster.id,
                        need_signal_id=sig.id
                    )
                    db.add(new_link)

            created_or_updated_clusters.append(cluster)

        db.commit()
        return created_or_updated_clusters
