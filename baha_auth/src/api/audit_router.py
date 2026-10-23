# Bộ định tuyến API cho nhật ký kiểm toán và vận hành an toàn (pha A09).
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from baha_auth.src.database import get_db
from baha_auth.src.api.deps import require_action, ActorContext
from baha_auth.src.models.entities import AuthorizationAuditEvent
from baha_auth.src.schemas.contracts import AuditEventOut

router = APIRouter(prefix="/authz/v1/audit", tags=["Nhật ký kiểm toán và an toàn"])

@router.get("/events", response_model=List[AuditEventOut])
def list_audit_events(
    limit: int = Query(50, ge=1, le=100),
    actor: ActorContext = Depends(require_action("audit.read")),
    db: Session = Depends(get_db)
):
    """
    Truy v?n nh?t k? ki?m to?n b?t bi?n thu?c ph?m vi qu?n l? c?a t?c nh?n.
    """
    events = db.query(AuthorizationAuditEvent).filter(
        AuthorizationAuditEvent.workspace_id == actor.workspace_id
    ).order_by(AuthorizationAuditEvent.timestamp.desc()).limit(limit).all()
    
    return events
