import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from src.models.entities import ProductionProject
from src.modules.media_studio.service import MediaStudioService
from src.schemas.contracts import ProductionProjectCreate
from fastapi import HTTPException


def test_project_creation_defaults_to_ai_video_and_can_create_auto_edit():
    ai_video = ProductionProjectCreate(title="Video AI")
    auto_edit = ProductionProjectCreate(title="Auto Edit", workflow_type="AUTO_EDIT")

    assert ai_video.workflow_type == "AI_VIDEO"
    assert auto_edit.workflow_type == "AUTO_EDIT"


def test_project_service_filters_workflows(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'projects.db'}")
    ProductionProject.__table__.create(engine)
    service = MediaStudioService()
    with Session(engine) as db:
        service.create_project(db, "workspace-1", "owner-1", ProductionProjectCreate(title="AI"))
        service.create_project(
            db, "workspace-1", "owner-1",
            ProductionProjectCreate(title="Auto", workflow_type="AUTO_EDIT"),
        )
        ai_projects = service.list_projects(db, "workspace-1", workflow_type="AI_VIDEO")
        auto_projects = service.list_projects(db, "workspace-1", workflow_type="AUTO_EDIT")

    assert [project.title for project in ai_projects] == ["AI"]
    assert [project.title for project in auto_projects] == ["Auto"]
    engine.dispose()


def test_project_workflow_migration_is_idempotent_and_keeps_auto_edit_results(tmp_path):
    from src.migrations.runner import migrate_production_project_workflow_up
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE production_projects (id VARCHAR(36) PRIMARY KEY, title VARCHAR(255) NOT NULL)"))
        connection.execute(text("CREATE TABLE media_assets (id VARCHAR(36) PRIMARY KEY, project_id VARCHAR(36), source_product VARCHAR(64))"))
        connection.execute(text("INSERT INTO production_projects (id, title) VALUES ('auto', 'Old Auto Edit'), ('ai', 'Old AI Video')"))
        connection.execute(text("INSERT INTO media_assets (id, project_id, source_product) VALUES ('out', 'auto', 'AUTO_EDIT')"))

    assert migrate_production_project_workflow_up(engine)
    assert migrate_production_project_workflow_up(engine)
    with engine.connect() as connection:
        rows = dict(connection.execute(text("SELECT id, workflow_type FROM production_projects")).all())
    assert rows == {"auto": "AUTO_EDIT", "ai": "AI_VIDEO"}
    assert "workflow_type" in {column["name"] for column in inspect(engine).get_columns("production_projects")}
    engine.dispose()


def test_auto_edit_endpoint_rejects_ai_video_project(monkeypatch):
    from src.modules.dieu_phoi_dung import bo_dinh_tuyen

    monkeypatch.setattr(
        bo_dinh_tuyen,
        "_kiem_tra_quyen_du_an",
        lambda *_: type("Project", (), {"workflow_type": "AI_VIDEO"})(),
    )
    with pytest.raises(HTTPException) as error:
        bo_dinh_tuyen.tu_dong_dung_video_dai(
            project_id="ai-project",
            req=bo_dinh_tuyen.TaoVideoDaiRequest(source_asset_id="source", idempotency_key="test-key-123"),
            db=None,
            ctx=type("Context", (), {"workspace_id": "workspace"})(),
        )

    assert error.value.status_code == 409
