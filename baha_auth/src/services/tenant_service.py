"""Thao tác tài nguyên trong workspace với ngữ cảnh quyền do máy chủ phân giải."""

import hashlib
import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from baha_auth.src.config import settings
from baha_auth.src.models.entities import BusinessResource
from baha_auth.src.policy.evaluator import ActorContext, ResourceContext, evaluate_permission
from baha_auth.src.services.nhat_ky_kiem_toan import write_audit_event


class TenantService:
    @staticmethod
    def _context(resource: BusinessResource) -> ResourceContext:
        return ResourceContext(
            workspace_id=resource.workspace_id,
            resource_id=resource.id,
            resource_type=resource.resource_type,
            org_unit_id=resource.org_unit_id,
            owner_id=resource.owner_id,
            creator_id=resource.creator_id,
            artifact_version=resource.artifact_version,
            content_hash=resource.content_hash,
            project_id=resource.project_id,
            brand_id=resource.brand_id,
            channel_id=resource.channel_id,
        )

    @staticmethod
    def _audit(
        db: Session,
        actor: ActorContext,
        action: str,
        decision: str,
        reason: str,
        resource_id: Optional[str] = None,
    ) -> None:
        write_audit_event(
            db,
            workspace_id=actor.workspace_id,
            actor_id=actor.user_id,
            actor_type="USER",
            action_key=action,
            decision=decision,
            reason=reason,
            policy_version=settings.policy_version,
            resource_type="BUSINESS_RESOURCE",
            resource_id=resource_id,
        )
        db.commit()

    @staticmethod
    def get_resource(db: Session, actor: ActorContext, resource_id: str) -> Optional[BusinessResource]:
        resource = db.query(BusinessResource).filter(
            BusinessResource.workspace_id == actor.workspace_id,
            BusinessResource.id == resource_id,
            BusinessResource.is_quarantined.is_(False),
        ).first()
        if resource is None:
            TenantService._audit(db, actor, "ideas.read", "DENY", "RESOURCE_NOT_FOUND_OR_CROSS_TENANT", resource_id)
            return None
        decision = evaluate_permission(actor, "ideas.read", TenantService._context(resource))
        if not decision.allowed:
            TenantService._audit(db, actor, "ideas.read", "DENY", decision.reason_code, resource_id)
            return None
        return resource

    @staticmethod
    def list_resources(db: Session, actor: ActorContext) -> List[BusinessResource]:
        resources = db.query(BusinessResource).filter(
            BusinessResource.workspace_id == actor.workspace_id,
            BusinessResource.is_quarantined.is_(False),
        ).all()
        return [
            resource for resource in resources
            if evaluate_permission(actor, "ideas.read", TenantService._context(resource)).allowed
        ]

    @staticmethod
    def create_resource(
        db: Session,
        actor: ActorContext,
        title: str,
        attempted_workspace_id: Optional[str] = None,
        search_text: Optional[str] = None,
    ) -> BusinessResource:
        del attempted_workspace_id
        context = ResourceContext(workspace_id=actor.workspace_id)
        decision = evaluate_permission(actor, "ideas.create", context)
        if not decision.allowed:
            TenantService._audit(db, actor, "ideas.create", "DENY", decision.reason_code)
            raise ValueError("RESOURCE_CREATE_NOT_AUTHORIZED")
        resource = BusinessResource(
            id=str(uuid.uuid4()),
            workspace_id=actor.workspace_id,
            owner_id=actor.user_id,
            creator_id=actor.user_id,
            title=title,
            search_text=search_text,
            content_hash=hashlib.sha256((title + (search_text or "")).encode("utf-8")).hexdigest(),
            artifact_version=1,
            is_quarantined=False,
        )
        db.add(resource)
        write_audit_event(
            db,
            workspace_id=actor.workspace_id,
            actor_id=actor.user_id,
            actor_type="USER",
            action_key="ideas.create",
            decision="ALLOW",
            reason="RESOURCE_CREATED",
            policy_version=decision.policy_version,
            resource_type="BUSINESS_RESOURCE",
            resource_id=resource.id,
        )
        db.commit()
        db.refresh(resource)
        return resource

    @staticmethod
    def search_resources(db: Session, actor: ActorContext, query_text: str) -> List[BusinessResource]:
        resources = db.query(BusinessResource).filter(
            BusinessResource.workspace_id == actor.workspace_id,
            BusinessResource.search_text.contains(query_text),
            BusinessResource.is_quarantined.is_(False),
        ).all()
        return [
            resource for resource in resources
            if evaluate_permission(actor, "ideas.read", TenantService._context(resource)).allowed
        ]

    @staticmethod
    def get_asset_download_url(db: Session, actor: ActorContext, resource_id: str) -> Optional[str]:
        resource = db.query(BusinessResource).filter(
            BusinessResource.workspace_id == actor.workspace_id,
            BusinessResource.id == resource_id,
            BusinessResource.is_quarantined.is_(False),
        ).first()
        if resource is None:
            TenantService._audit(db, actor, "media.read", "DENY", "RESOURCE_NOT_FOUND_OR_CROSS_TENANT", resource_id)
            return None
        decision = evaluate_permission(actor, "media.read", TenantService._context(resource))
        if not decision.allowed:
            TenantService._audit(db, actor, "media.read", "DENY", decision.reason_code, resource_id)
            return None
        # Không có nhà cung cấp ký URL được cấu hình; tuyệt đối không tự tạo URL dùng được.
        return None

    @staticmethod
    def quarantine_orphaned_resource(
        db: Session,
        resource_id: str,
        *,
        system_maintenance: bool = False,
    ) -> Optional[BusinessResource]:
        if not system_maintenance:
            raise ValueError("SYSTEM_MAINTENANCE_AUTHORIZATION_REQUIRED")
        resource = db.query(BusinessResource).filter(
            BusinessResource.id == resource_id,
            BusinessResource.workspace_id.is_(None),
        ).first()
        if resource:
            resource.is_quarantined = True
            write_audit_event(
                db, workspace_id=None, actor_id=None, actor_type="SYSTEM", action_key="resource.quarantine",
                decision="ALLOW", reason="ORPHAN_RESOURCE_QUARANTINED", policy_version=settings.policy_version,
                resource_type="BUSINESS_RESOURCE", resource_id=resource.id,
            )
            db.commit()
            db.refresh(resource)
        return resource

    @staticmethod
    def aggregate_view_counts(db: Session, actor: ActorContext) -> int:
        return sum(resource.view_count for resource in TenantService.list_resources(db, actor))

    @staticmethod
    def update_resource(db: Session, actor: ActorContext, resource_id: str, new_title: str) -> bool:
        resource = db.query(BusinessResource).filter(
            BusinessResource.workspace_id == actor.workspace_id,
            BusinessResource.id == resource_id,
            BusinessResource.is_quarantined.is_(False),
        ).first()
        if resource is None:
            TenantService._audit(db, actor, "ideas.edit", "DENY", "RESOURCE_NOT_FOUND_OR_CROSS_TENANT", resource_id)
            return False
        decision = evaluate_permission(actor, "ideas.edit", TenantService._context(resource))
        if not decision.allowed:
            TenantService._audit(db, actor, "ideas.edit", "DENY", decision.reason_code, resource_id)
            return False
        resource.title = new_title
        resource.artifact_version += 1
        resource.content_hash = hashlib.sha256(
            (new_title + (resource.search_text or "")).encode("utf-8")
        ).hexdigest()
        write_audit_event(
            db,
            workspace_id=actor.workspace_id,
            actor_id=actor.user_id,
            actor_type="USER",
            action_key="ideas.edit",
            decision="ALLOW",
            reason="RESOURCE_UPDATED",
            policy_version=decision.policy_version,
            resource_type="BUSINESS_RESOURCE",
            resource_id=resource.id,
            safe_metadata={"artifact_version": resource.artifact_version},
        )
        db.commit()
        return True
