import uuid
from datetime import datetime, timedelta, timezone

from src.database import Base, SessionLocal, engine
from src.models.entities import ContentVideoRun
from src.modules.tao_video_noi_dung.runner import _claim_next_run


def test_worker_chi_nhan_run_thuoc_workspace_da_cau_hinh(monkeypatch):
    workspace_id = str(uuid.uuid4())
    other_workspace_id = str(uuid.uuid4())
    monkeypatch.setenv("SIN_WORKSPACE_ID", workspace_id)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    other_run_id = str(uuid.uuid4())
    target_run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    for run_id, run_workspace, created_at in (
        (other_run_id, other_workspace_id, now - timedelta(seconds=1)),
        (target_run_id, workspace_id, now),
    ):
        db.add(ContentVideoRun(
            id=run_id,
            workspace_id=run_workspace,
            project_id=str(uuid.uuid4()),
            plan_id=str(uuid.uuid4()),
            plan_revision=1,
            storyboard_sha256="a" * 64,
            style_snapshot_sha256="b" * 64,
            approval_sha256="c" * 64,
            idempotency_key=run_id,
            status="QUEUED",
            steps_json="[]",
            output_asset_ids_json="[]",
            created_by=str(uuid.uuid4()),
            created_at=created_at,
        ))
    db.commit()

    claimed = _claim_next_run(db, str(uuid.uuid4()))

    assert claimed is not None
    assert claimed.id == target_run_id
    assert db.get(ContentVideoRun, other_run_id).status == "QUEUED"
    db.close()
