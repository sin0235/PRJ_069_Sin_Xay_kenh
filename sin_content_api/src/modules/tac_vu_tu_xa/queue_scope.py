"""Giữ job nhập từ NAS ở lịch sử; worker dev chỉ xử lý job tạo từ mốc chuyển đổi."""
import os
from datetime import datetime, timezone
from sqlalchemy import event
from sqlalchemy.orm import with_loader_criteria


def restrict_dev_queue(session):
    if os.getenv('REMOTE_COMPUTE_MODE') != 'github':
        return
    value = os.environ.get('LOCAL_DEV_JOB_CUTOFF_UTC')
    if not value:
        raise RuntimeError('LOCAL_DEV_JOB_CUTOFF_REQUIRED')
    cutoff = datetime.fromisoformat(value).astimezone(timezone.utc).replace(tzinfo=None)
    from src.models.entities import AIGenerationJob, ContentVideoRun
    def restrict(state):
        if state.is_orm_statement:
            state.statement = state.statement.options(
                with_loader_criteria(AIGenerationJob, AIGenerationJob.created_at >= cutoff, include_aliases=True),
                with_loader_criteria(ContentVideoRun, ContentVideoRun.created_at >= cutoff, include_aliases=True),
            )
    event.listen(session, 'do_orm_execute', restrict)
