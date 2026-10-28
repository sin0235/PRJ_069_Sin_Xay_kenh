"""Ngăn worker đã mất quyền sở hữu ghi kết quả ORM."""
from datetime import datetime, timezone

from sqlalchemy import event, select
from src.models.entities import ContentVideoWorkerLease


class WorkerLeaseLost(RuntimeError):
    pass


def fence_session(db, token: str):
    def before_flush(session, flush_context, instances):
        owned = session.connection().execute(select(ContentVideoWorkerLease.token).where(
            ContentVideoWorkerLease.name == "content-video-flow",
            ContentVideoWorkerLease.token == token,
            ContentVideoWorkerLease.expires_at > datetime.now(timezone.utc),
        )).scalar_one_or_none()
        if owned != token:
            raise WorkerLeaseLost("WORKER_LEASE_LOST")
    event.listen(db, "before_flush", before_flush)
