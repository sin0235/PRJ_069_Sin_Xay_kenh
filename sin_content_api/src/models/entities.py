import json
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from src.database import Base

def generate_uuid():
    return str(uuid.uuid4())

def utc_now():
    return datetime.now(timezone.utc)

class Workspace(Base):
    __tablename__ = "workspaces"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    
    memberships = relationship("Membership", back_populates="workspace", cascade="all, delete-orphan")
    briefs = relationship("BrandBriefVersion", back_populates="workspace", cascade="all, delete-orphan")
    source_records = relationship("SourceRecord", back_populates="workspace", cascade="all, delete-orphan")
    quarantine_records = relationship("QuarantineRecord", back_populates="workspace", cascade="all, delete-orphan")
    idea_cards = relationship("IdeaCard", back_populates="workspace", cascade="all, delete-orphan")
    research_runs = relationship("ResearchRun", back_populates="workspace", cascade="all, delete-orphan")
    evidence_excerpts = relationship("EvidenceExcerpt", back_populates="workspace", cascade="all, delete-orphan")
    topic_clusters = relationship("TopicCluster", back_populates="workspace", cascade="all, delete-orphan")

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=True) # nullable=True de phu hop voi moi truong offline / test
    full_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    
    memberships = relationship("Membership", back_populates="user", cascade="all, delete-orphan")

class Membership(Base):
    __tablename__ = "memberships"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(50), nullable=False, default="viewer") # owner, admin, researcher, editor, reviewer, viewer
    created_at = Column(DateTime, default=utc_now, nullable=False)
    
    workspace = relationship("Workspace", back_populates="memberships")
    user = relationship("User", back_populates="memberships")

class BrandBriefVersion(Base):
    __tablename__ = "brand_brief_versions"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    brand_name = Column(String(255), nullable=False)
    objective = Column(Text, nullable=False)
    voice_description = Column(Text, nullable=False)
    language = Column(String(10), nullable=False, default="vi-VN")
    
    # Tach biet ro rang Current Audience va Target Audience
    current_audience = Column(Text, nullable=False)
    target_audience = Column(Text, nullable=False)
    
    # Chu de duoc phep va chu de bi cam (Brand Safety)
    topics_included_json = Column(Text, nullable=False, default="[]") # JSON list of strings
    topics_excluded_json = Column(Text, nullable=False, default="[]") # JSON list of strings (bat buoc khong rong)
    production_limits_json = Column(Text, nullable=False, default="[]")
    
    # Vong doi trang thai: DRAFT -> IN_REVIEW -> APPROVED -> SUPERSEDED, CHANGES_REQUESTED -> DRAFT
    status = Column(String(50), nullable=False, default="DRAFT")
    approved_by_user_id = Column(String(36), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    
    workspace = relationship("Workspace", back_populates="briefs")
    idea_cards = relationship("IdeaCard", back_populates="brief_version")
    audience_segments = relationship("AudienceSegment", back_populates="brief_version", cascade="all, delete-orphan")
    allowed_facts = relationship("AllowedFact", back_populates="brief_version", cascade="all, delete-orphan")
    research_runs = relationship("ResearchRun", back_populates="brief_version", cascade="all, delete-orphan")

    @property
    def topics_included(self):
        import json
        try:
            return json.loads(self.topics_included_json or "[]")
        except Exception:
            return []

    @property
    def topics_excluded(self):
        import json
        try:
            return json.loads(self.topics_excluded_json or "[]")
        except Exception:
            return []

    @property
    def production_limits(self):
        import json
        try:
            return json.loads(self.production_limits_json or "[]")
        except Exception:
            return []

class AudienceSegment(Base):
    __tablename__ = "audience_segments"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    brief_version_id = Column(String(36), ForeignKey("brand_brief_versions.id"), nullable=False, index=True)
    label = Column(String(255), nullable=False)
    contexts_json = Column(Text, nullable=False, default="[]") # Tinh huong su dung
    needs_json = Column(Text, nullable=False, default="[]") # Noi dau / mong muon
    disallowed_inferences_json = Column(Text, nullable=False, default="[]") # Suy luan bi cam
    awareness_stage = Column(String(50), nullable=False, default="PROBLEM_AWARE")
    created_at = Column(DateTime, default=utc_now, nullable=False)
    
    brief_version = relationship("BrandBriefVersion", back_populates="audience_segments")

class AllowedFact(Base):
    __tablename__ = "allowed_facts"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    brief_version_id = Column(String(36), ForeignKey("brand_brief_versions.id"), nullable=False, index=True)
    claim_text = Column(Text, nullable=False)
    fact_type = Column(String(50), nullable=False, default="PRODUCT_SPECS") # PRODUCT_SPECS, CLINICAL_TRIAL, PRICING, POLICY
    source_citation = Column(Text, nullable=False) # Tai lieu chung minh / SKU / URL noi bo
    verification_status = Column(String(50), nullable=False, default="VERIFIED") # VERIFIED, EXEMPTED
    created_at = Column(DateTime, default=utc_now, nullable=False)
    
    brief_version = relationship("BrandBriefVersion", back_populates="allowed_facts")

class SourceRecord(Base):
    """Canonical Source Record. Multiple observations from different providers link here."""
    __tablename__ = "source_records"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    provider_id = Column(String(50), nullable=False) # primary or initial provider
    raw_external_id = Column(String(255), nullable=False, index=True)
    canonical_url = Column(String(512), nullable=True, index=True)
    title = Column(Text, nullable=True)
    caption = Column(Text, nullable=True)
    synthetic = Column(Boolean, default=False, nullable=False)
    rights_basis = Column(String(100), nullable=False, default="customer_supplied")
    observed_at = Column(DateTime, default=utc_now, nullable=False)
    is_purged = Column(Boolean, default=False, nullable=False)
    purged_at = Column(DateTime, nullable=True)
    is_paid = Column(Boolean, default=False, nullable=False)
    channel_id = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    
    workspace = relationship("Workspace", back_populates="source_records")
    metric_snapshots = relationship("MetricSnapshot", back_populates="source_record", cascade="all, delete-orphan")
    observations = relationship("SourceObservation", back_populates="source_record", cascade="all, delete-orphan")
    evidence_excerpts = relationship("EvidenceExcerpt", back_populates="source_record", cascade="all, delete-orphan")

    @property
    def source_url(self):
        return self.canonical_url

    @source_url.setter
    def source_url(self, val):
        self.canonical_url = val

class SourceObservation(Base):
    """Source Observation for Provenance & Multi-Source Lineage (P04)."""
    __tablename__ = "source_observations"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    source_record_id = Column(String(36), ForeignKey("source_records.id"), nullable=False, index=True)
    observation_id = Column(String(100), nullable=False, index=True) # Unique observation identifier from provider
    provider_id = Column(String(50), nullable=False) # customer_import, tiktok_official, test_fixture
    observed_at = Column(DateTime, default=utc_now, nullable=False)
    raw_payload_json = Column(Text, nullable=True)
    rights_basis = Column(String(100), nullable=False, default="customer_supplied")
    retention_days = Column(Integer, nullable=False, default=90)
    is_purged = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    
    source_record = relationship("SourceRecord", back_populates="observations")

class MetricSnapshot(Base):
    """Metric Snapshot. view_count is strictly nullable (NULL / NOT_AVAILABLE, never coerced to 0 unless observed 0)."""
    __tablename__ = "metric_snapshots"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=True, index=True)
    source_record_id = Column(String(36), ForeignKey("source_records.id"), nullable=False, index=True)
    observation_id = Column(String(100), nullable=True, index=True)
    observed_at = Column(DateTime, default=utc_now, nullable=False)
    view_count = Column(Integer, nullable=True) # Strictly NULL if missing, 0 ONLY if explicitly observed as 0
    like_count = Column(Integer, nullable=True)
    comment_count = Column(Integer, nullable=True)
    share_count = Column(Integer, nullable=True)
    is_paid = Column(Boolean, default=False, nullable=False)
    channel_id = Column(String(100), nullable=True, index=True)
    synthetic = Column(Boolean, default=False, nullable=False)
    
    source_record = relationship("SourceRecord", back_populates="metric_snapshots")

class QuarantineRecord(Base):
    __tablename__ = "quarantine_records"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    provider_id = Column(String(50), nullable=False)
    raw_payload_json = Column(Text, nullable=False)
    error_reason = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    
    workspace = relationship("Workspace", back_populates="quarantine_records")

class EvidenceExcerpt(Base):
    """Evidence Excerpt linked to SourceRecord (P06)."""
    __tablename__ = "evidence_excerpts"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    source_record_id = Column(String(36), ForeignKey("source_records.id"), nullable=False, index=True)
    excerpt_text = Column(Text, nullable=False)
    excerpt_type = Column(String(50), nullable=False, default="CAPTION") # CAPTION, COMMENT, TRANSCRIPT
    author_id = Column(String(100), nullable=True)
    observed_at = Column(DateTime, default=utc_now, nullable=False)
    is_sanitized = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    
    workspace = relationship("Workspace", back_populates="evidence_excerpts")
    source_record = relationship("SourceRecord", back_populates="evidence_excerpts")
    need_signals = relationship("NeedSignal", back_populates="evidence_excerpt", cascade="all, delete-orphan")

class NeedSignal(Base):
    """Need Signal with Quote Attribution and Observed/Inferred Distinction (P06)."""
    __tablename__ = "need_signals"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    evidence_excerpt_id = Column(String(36), ForeignKey("evidence_excerpts.id"), nullable=False, index=True)
    intent_group = Column(String(50), nullable=False) # PROBLEMS, OBJECTIONS, COMPARISONS, etc.
    need_category = Column(String(100), nullable=False) # PACKAGING_LEAKAGE, etc.
    signal_text = Column(Text, nullable=False)
    quote_text = Column(Text, nullable=False) # Exact unadulterated quote from user/content
    observed_vs_inferred = Column(String(50), nullable=False, default="OBSERVED_DIRECT") # OBSERVED_DIRECT, INFERRED_UNVERIFIED
    confidence_score = Column(Float, nullable=False, default=1.0)
    demographic_inferences_json = Column(Text, nullable=False, default="[]") # T062: Log unsupported demographic claims
    created_at = Column(DateTime, default=utc_now, nullable=False)
    
    evidence_excerpt = relationship("EvidenceExcerpt", back_populates="need_signals")
    cluster_links = relationship("TopicClusterSignal", back_populates="need_signal", cascade="all, delete-orphan")

class TopicCluster(Base):
    """Topic Cluster grouping related NeedSignals (P06 / T060)."""
    __tablename__ = "topic_clusters"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    cluster_label = Column(String(255), nullable=False)
    intent_group = Column(String(50), nullable=False)
    need_category = Column(String(100), nullable=False)
    signal_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    
    workspace = relationship("Workspace", back_populates="topic_clusters")
    signals = relationship("TopicClusterSignal", back_populates="topic_cluster", cascade="all, delete-orphan")

class TopicClusterSignal(Base):
    """Join table linking TopicCluster to NeedSignal."""
    __tablename__ = "topic_cluster_signals"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    cluster_id = Column(String(36), ForeignKey("topic_clusters.id"), nullable=False, index=True)
    need_signal_id = Column(String(36), ForeignKey("need_signals.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    
    topic_cluster = relationship("TopicCluster", back_populates="signals")
    need_signal = relationship("NeedSignal", back_populates="cluster_links")

class ResearchRun(Base):
    """Execution of a ResearchPlan (P05)."""
    __tablename__ = "research_runs"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    brief_version_id = Column(String(36), ForeignKey("brand_brief_versions.id"), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="PLANNED") # PLANNED, RUNNING, COMPLETED, FAILED
    plan_json = Column(Text, nullable=False) # Serialized ResearchPlan
    created_at = Column(DateTime, default=utc_now, nullable=False)
    
    workspace = relationship("Workspace", back_populates="research_runs")
    brief_version = relationship("BrandBriefVersion", back_populates="research_runs")

class GoldCandidate(Base):
    """Human-Annotated Gold Dataset for Retrieval Benchmark (P05)."""
    __tablename__ = "gold_candidates"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    brief_id = Column(String(36), nullable=False, index=True)
    brief_name = Column(String(255), nullable=False)
    candidate_title = Column(Text, nullable=False)
    content_excerpt = Column(Text, nullable=False)
    source_url = Column(String(512), nullable=False)
    evidence_tier = Column(String(50), nullable=False) # EVIDENCE_BACKED, LIMITED_SIGNAL, HYPOTHESIS
    reviewer_1_label = Column(String(50), nullable=False) # RELEVANT, BORDERLINE, IRRELEVANT
    reviewer_1_score = Column(Integer, nullable=False) # 0-10
    reviewer_2_label = Column(String(50), nullable=False)
    reviewer_2_score = Column(Integer, nullable=False)
    adjudication_label = Column(String(50), nullable=False) # Final adjudicated label
    final_score = Column(Integer, nullable=False) # Final adjudicated score
    adjudication_reason = Column(Text, nullable=False)
    has_veto_violation = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

class IdeaCard(Base):
    __tablename__ = "idea_cards"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    brief_version_id = Column(String(36), ForeignKey("brand_brief_versions.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    target_need = Column(Text, nullable=False)
    hook = Column(Text, nullable=False)
    content_angle = Column(Text, nullable=False)
    confidence_tier = Column(String(50), nullable=False, default="EVIDENCE_BACKED") # EVIDENCE_BACKED, LIMITED_SIGNAL, HYPOTHESIS
    status = Column(String(50), nullable=False, default="DRAFT") # DRAFT, NEEDS_EVIDENCE, READY_FOR_REVIEW, APPROVED, REJECTED
    overall_score = Column(Float, nullable=False, default=0.0)
    evidence_excerpt_ids_json = Column(Text, nullable=False, default="[]")
    citations_json = Column(Text, nullable=False, default="[]")
    duplicate_warning = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    creator_id = Column(String(36), nullable=True, index=True)
    version = Column(Integer, default=1, nullable=False)
    review_reason = Column(Text, nullable=True)
    reviewed_by = Column(String(36), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    synthetic = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    
    workspace = relationship("Workspace", back_populates="idea_cards")
    brief_version = relationship("BrandBriefVersion", back_populates="idea_cards")
    scripts = relationship("ScriptDraftVersion", back_populates="idea_card", cascade="all, delete-orphan")

    @property
    def evidence_excerpt_ids(self):
        import json
        try:
            return json.loads(self.evidence_excerpt_ids_json or "[]")
        except Exception:
            return []

    @evidence_excerpt_ids.setter
    def evidence_excerpt_ids(self, val):
        import json
        self.evidence_excerpt_ids_json = json.dumps(val or [])

    @property
    def citations(self):
        import json
        try:
            return json.loads(self.citations_json or "[]")
        except Exception:
            return []

    @citations.setter
    def citations(self, val):
        import json
        self.citations_json = json.dumps(val or [])

class ScriptDraftVersion(Base):
    __tablename__ = "script_draft_versions"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    idea_id = Column(String(36), ForeignKey("idea_cards.id"), nullable=False, index=True)
    created_by_user_id = Column(String(36), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    title = Column(String(255), nullable=False)
    target_duration_seconds = Column(Integer, nullable=False, default=45)
    hook_variants_json = Column(Text, nullable=True, default="[]") # JSON array of strings
    blocks_json = Column(Text, nullable=False, default="[]") # JSON array of ScriptBlock
    claims_json = Column(Text, nullable=False, default="[]") # JSON array of ClaimCheck
    status = Column(String(50), nullable=False, default="DRAFT") # DRAFT, NEEDS_FACT_CHECK, READY_FOR_REVIEW, APPROVED, REJECTED, SUPERSEDED
    approved_by_user_id = Column(String(36), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    
    idea_card = relationship("IdeaCard", back_populates="scripts")

    @property
    def hook_variants(self):
        import json
        try:
            return json.loads(self.hook_variants_json or "[]")
        except Exception:
            return []

    @hook_variants.setter
    def hook_variants(self, val):
        import json
        self.hook_variants_json = json.dumps(val or [])

    @property
    def blocks(self):
        import json
        try:
            return json.loads(self.blocks_json or "[]")
        except Exception:
            return []

    @blocks.setter
    def blocks(self, val):
        import json
        self.blocks_json = json.dumps(val or [])

    @property
    def claims(self):
        import json
        try:
            return json.loads(self.claims_json or "[]")
        except Exception:
            return []

    @claims.setter
    def claims(self, val):
        import json
        self.claims_json = json.dumps(val or [])

    @property
    def actual_duration_seconds(self) -> int:
        return sum(int(b.get("duration_seconds", 0)) for b in self.blocks)

    @property
    def duration_tolerance_passed(self) -> bool:
        # Dung sai +/- 3 giay so voi target duration
        return abs(self.actual_duration_seconds - self.target_duration_seconds) <= 3

    @property
    def blocking_claims_count(self) -> int:
        return sum(1 for c in self.claims if c.get("verification_status") in ["BLOCKING", "NEEDS_FACT_CHECK"])

class AuditEvent(Base):
    __tablename__ = "audit_events"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), nullable=False, index=True)
    actor_id = Column(String(36), nullable=False)
    event_type = Column(String(100), nullable=False) # LOGIN, BRIEF_APPROVE, IDEA_APPROVE, DATA_RETENTION_PURGE, SYNTHETIC_DATA_REJECTED, etc.
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)


# P11 Models: Owned Channel Feedback Loop & Trend Velocity
class OwnedChannel(Base):
    __tablename__ = "owned_channels"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    channel_id = Column(String(100), nullable=False, index=True)
    channel_name = Column(String(255), nullable=False)
    platform = Column(String(50), nullable=False, default="tiktok")
    status = Column(String(50), nullable=False, default="DISCONNECTED") # CONNECTED, FEATURE_UNAVAILABLE, NOT_CONNECTED
    oauth_scopes_json = Column(Text, nullable=False, default="[]")
    has_metrics_scope = Column(Boolean, default=False, nullable=False)
    follower_count = Column(Integer, nullable=True)
    video_count = Column(Integer, nullable=True)
    profile_views_7d = Column(Integer, nullable=True)
    metadata_json = Column(Text, nullable=True, default="{}")
    verified_at = Column(DateTime, nullable=True)
    connected_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    @property
    def oauth_scopes(self):
        try:
            return json.loads(self.oauth_scopes_json or "[]")
        except Exception:
            return []

class TrendVelocityObservation(Base):
    __tablename__ = "trend_velocity_observations"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    source_record_id = Column(String(36), ForeignKey("source_records.id"), nullable=False, index=True)
    from_observation_id = Column(String(100), nullable=False)
    to_observation_id = Column(String(100), nullable=False)
    metric_name = Column(String(50), nullable=False, default="VIEW_COUNT")
    from_value = Column(Integer, nullable=True)
    to_value = Column(Integer, nullable=True)
    delta_value = Column(Integer, nullable=True)
    delta_days = Column(Float, nullable=False)
    velocity_per_day = Column(Float, nullable=True)
    growth_rate = Column(Float, nullable=True)
    rate_status = Column(String(50), nullable=False, default="VALID") # VALID, NOT_AVAILABLE
    is_paid = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

class PublishedContentLink(Base):
    __tablename__ = "published_content_links"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    script_draft_version_id = Column(String(36), ForeignKey("script_draft_versions.id"), nullable=False, index=True)
    platform = Column(String(50), nullable=False, default="tiktok")
    external_post_id = Column(String(100), nullable=False, index=True)
    external_post_url = Column(String(500), nullable=False)
    channel_id = Column(String(100), nullable=True, index=True)
    is_paid = Column(Boolean, default=False, nullable=False)
    status = Column(String(50), nullable=False, default="ACTIVE")
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    detached_at = Column(DateTime, nullable=True)

    snapshots = relationship("PerformanceSnapshot", back_populates="published_link", cascade="all, delete-orphan")
    learning_signals = relationship("LearningSignal", back_populates="published_link", cascade="all, delete-orphan")

class PerformanceSnapshot(Base):
    __tablename__ = "performance_snapshots"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    published_content_link_id = Column(String(36), ForeignKey("published_content_links.id"), nullable=False, index=True)
    view_count = Column(Integer, nullable=True)
    like_count = Column(Integer, nullable=True)
    comment_count = Column(Integer, nullable=True)
    share_count = Column(Integer, nullable=True)
    watch_time_avg_seconds = Column(Float, nullable=True)
    completion_rate = Column(Float, nullable=True)
    snapshot_source = Column(String(50), nullable=False, default="TIKTOK_OFFICIAL_API")
    is_paid = Column(Boolean, default=False, nullable=False)
    observed_at = Column(DateTime, default=utc_now, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    published_link = relationship("PublishedContentLink", back_populates="snapshots")

class LearningSignal(Base):
    __tablename__ = "learning_signals"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    published_content_link_id = Column(String(36), ForeignKey("published_content_links.id"), nullable=False, index=True)
    signal_type = Column(String(50), nullable=False)
    score = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False, default=1.0)
    formula_applied = Column(String(255), nullable=False)
    limitations_note = Column(Text, nullable=True)
    insight_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    published_link = relationship("PublishedContentLink", back_populates="learning_signals")
    experiment_suggestions = relationship("ExperimentSuggestion", back_populates="learning_signal", cascade="all, delete-orphan")


class ExperimentSuggestion(Base):
    """Experiment Suggestion generated from verified learning signals (P11)."""
    __tablename__ = "experiment_suggestions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    based_on_signal_id = Column(String(36), ForeignKey("learning_signals.id"), nullable=False, index=True)
    hypothesis = Column(Text, nullable=False)
    suggested_action = Column(Text, nullable=False)
    status = Column(String(30), default="PROPOSED", nullable=False) # PROPOSED, ACCEPTED, REJECTED, EXECUTED
    created_at = Column(DateTime, default=utc_now, nullable=False)

    learning_signal = relationship("LearningSignal", back_populates="experiment_suggestions")


class WorkspaceBudget(Base):
    __tablename__ = "workspace_budgets"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, unique=True, index=True)
    allocated_units = Column(Float, nullable=False, default=100.0)
    reserved_units = Column(Float, nullable=False, default=0.0)
    spent_units = Column(Float, nullable=False, default=0.0)
    hard_limit_units = Column(Float, nullable=False, default=100.0)
    alert_threshold_percent = Column(Float, default=80.0)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

class CostLedger(Base):
    __tablename__ = "cost_ledgers"
    __table_args__ = (
        UniqueConstraint("workspace_id", "idempotency_key", name="uq_workspace_idempotency_key"),
    )
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    task_id = Column(String(100), nullable=False, index=True)
    idempotency_key = Column(String(100), nullable=False, index=True)
    action_type = Column(String(50), nullable=False)
    estimated_units = Column(Float, nullable=False)
    actual_units = Column(Float, nullable=True)
    status = Column(String(50), nullable=False, default="RESERVED") # RESERVED, COMMITTED, REFUSED, REFUNDED
    vendor_reported_units = Column(Float, nullable=True)
    discrepancy_alert = Column(Boolean, default=False, nullable=False)
    output_artifact_id = Column(String(100), nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)


# ==========================================
# PHASE P13 ENTITIES: PRODUCTION CANARY AND ROLLBACK
# ==========================================

class CanaryDeployment(Base):
    __tablename__ = "canary_deployments"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    tenant_name = Column(String(255), nullable=False)
    human_approval_id = Column(String(100), nullable=False) # Ma van ban phe duyet
    signed_rights_reference = Column(String(255), nullable=False) # Thoa thuan ban quyen nguon da ky
    status = Column(String(50), nullable=False, default="CANARY_ACTIVE") # CANARY_ACTIVE, ROLLED_BACK, GRADUATED
    traffic_percentage = Column(Float, nullable=False, default=5.0) # Ty le luu luong canary (vd 5%)
    is_rollback_ready = Column(Boolean, default=True, nullable=False)
    rollback_reason = Column(String(255), nullable=True)
    deployed_at = Column(DateTime, default=utc_now, nullable=False)
    rolled_back_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

class CanaryResearchRun(Base):
    __tablename__ = "canary_research_runs"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    canary_deployment_id = Column(String(36), ForeignKey("canary_deployments.id"), nullable=False, index=True)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    brief_version_id = Column(String(36), ForeignKey("brand_brief_versions.id"), nullable=False, index=True)
    run_status = Column(String(50), nullable=False, default="COMPLETED") # RUNNING, COMPLETED, ROLLED_BACK, FAILED
    quota_cost_units = Column(Float, nullable=False, default=1.0)
    real_source_ids_json = Column(Text, nullable=False, default="[]") # T130: Records real source IDs
    data_lineage_json = Column(Text, nullable=False, default="{}") # T130: Lineage
    review_output_json = Column(Text, nullable=False, default="{}") # T130: Review output
    is_rollback_ready = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    @property
    def real_source_ids(self):
        try:
            return json.loads(self.real_source_ids_json or "[]")
        except Exception:
            return []

    @property
    def data_lineage(self):
        try:
            return json.loads(self.data_lineage_json or "{}")
        except Exception:
            return {}

    @property
    def review_output(self):
        try:
            return json.loads(self.review_output_json or "{}")
        except Exception:
            return {}

class ProviderAccessGrant(Base):
    __tablename__ = "provider_access_grants"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    provider_id = Column(String(50), nullable=False, index=True) # TIKTOK_OFFICIAL, YOUTUBE_OFFICIAL
    status = Column(String(50), nullable=False, default="ACTIVE") # ACTIVE, REVOKED, UNAVAILABLE
    rights_basis = Column(String(100), nullable=False, default="SIGNED_LICENSE")
    revoked_at = Column(DateTime, nullable=True)
    revocation_reason = Column(String(255), nullable=True)
    no_bypass_enforced = Column(Boolean, default=True, nullable=False) # T131: Cam tuyet doi bypass thay the
    created_at = Column(DateTime, default=utc_now, nullable=False)


# ==============================================================================
# P1 Production Workflow / BAHA AI Media Studio Entities (MEDIA_P1)
# ==============================================================================

class ProductionProject(Base):
    __tablename__ = "production_projects"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    script_id = Column(String(36), ForeignKey("script_draft_versions.id"), nullable=True, index=True)
    status = Column(String(50), nullable=False, default="DRAFT") # DRAFT, IN_PRODUCTION, REVIEW, APPROVED, PUBLISH_READY

    created_by = Column(String(36), nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class ContentVideoPlan(Base):
    __tablename__ = "content_video_plans"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("production_projects.id"), nullable=False, index=True)
    revision = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False, default="DRAFT")
    source_content = Column(Text, nullable=False)
    content_sha256 = Column(String(64), nullable=False)
    target_duration_seconds = Column(Integer, nullable=False)
    style_snapshot_json = Column(Text, nullable=False)
    style_snapshot_sha256 = Column(String(64), nullable=False)
    storyboard_json = Column(Text, nullable=False)
    storyboard_sha256 = Column(String(64), nullable=False)
    llm_model = Column(String(100), nullable=False)
    created_by = Column(String(36), nullable=False)
    approved_by = Column(String(36), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("project_id", "revision", name="uq_content_video_plan_revision"),
    )


class ContentVideoRun(Base):
    __tablename__ = "content_video_runs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("production_projects.id"), nullable=False, index=True)
    plan_id = Column(String(36), ForeignKey("content_video_plans.id"), nullable=False, index=True)
    voice_asset_id = Column(String(36), ForeignKey("media_assets.id"), nullable=True)
    tts_config_json = Column(Text, nullable=True)
    plan_revision = Column(Integer, nullable=False)
    storyboard_sha256 = Column(String(64), nullable=False)
    style_snapshot_sha256 = Column(String(64), nullable=False)
    approval_sha256 = Column(String(64), nullable=False)
    idempotency_key = Column(String(128), nullable=False, unique=True)
    status = Column(String(40), nullable=False, default="QUEUED")
    current_step = Column(String(64), nullable=True)
    steps_json = Column(Text, nullable=False, default="[]")
    output_asset_ids_json = Column(Text, nullable=False, default="[]")
    final_asset_id = Column(String(36), ForeignKey("media_assets.id"), nullable=True)
    qc_report_json = Column(Text, nullable=True)
    error_code = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    lease_token = Column(String(36), nullable=True)
    lease_expires_at = Column(DateTime, nullable=True)
    created_by = Column(String(36), nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)


class ContentVideoWorkerLease(Base):
    __tablename__ = "content_video_worker_leases"

    name = Column(String(64), primary_key=True)
    token = Column(String(36), nullable=True)
    expires_at = Column(DateTime, nullable=True)

class ProductionTask(Base):
    __tablename__ = "production_tasks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("production_projects.id"), nullable=False, index=True)
    task_type = Column(String(50), nullable=False) # VOICEOVER, BROLL, MUSIC, TIMELINE, QC
    status = Column(String(50), nullable=False, default="PENDING") # PENDING, RUNNING, COMPLETED, FAILED
    assigned_to = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

class MediaAsset(Base):
    __tablename__ = "media_assets"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("production_projects.id"), nullable=True, index=True)
    storage_key = Column(String(512), nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    byte_size = Column(Integer, nullable=False)
    mime_detected = Column(String(100), nullable=False)
    duration_ms = Column(Integer, nullable=True)
    source_product = Column(String(50), nullable=False) # UPLOAD, FLOW_MUSIC, LYRIA_API, GEMINI_IMAGE, GEMINI_VIDEO, GEMINI_TTS
    original_filename = Column(String(255), nullable=True)
    license_record_id = Column(String(36), nullable=True)
    approval_state = Column(String(50), nullable=False, default="UNREVIEWED") # UNREVIEWED, APPROVED, REJECTED, PUBLISH_READY
    parent_asset_id = Column(String(36), ForeignKey("media_assets.id"), nullable=True)
    created_by = Column(String(36), nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

class AIGenerationJob(Base):
    __tablename__ = "ai_generation_jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("production_projects.id"), nullable=True, index=True)
    asset_type = Column(String(50), nullable=False) # IMAGE, VIDEO, AUDIO, MUSIC
    provider = Column(String(50), nullable=False) # GOOGLE_OFFICIAL, FLOW_MUSIC_ASSISTED, FAKE_PROVIDER
    provider_mode = Column(String(50), nullable=False) # OFFICIAL_API, SUBSCRIPTION_ASSISTED, TEST_MOCK
    model_id = Column(String(100), nullable=False)
    idempotency_key = Column(String(128), unique=True, nullable=False, index=True)
    state = Column(String(50), nullable=False, default="QUEUED") # DRAFT, QUEUED, RUNNING, SUCCEEDED, FAILED, CANCELLED, EXPIRED
    request_payload_json = Column(Text, nullable=False, default="{}")
    estimated_cost = Column(Float, nullable=False, default=0.0)
    actual_cost = Column(Float, nullable=False, default=0.0)
    cost_currency = Column(String(10), nullable=False, default="USD")
    credits_source = Column(String(50), nullable=False, default="API_BILLING") # API_BILLING, FLOW_MUSIC_PLUS, MANUAL_RECORD
    output_asset_ids_json = Column(Text, nullable=False, default="[]")
    retry_count = Column(Integer, nullable=False, default=0)
    error_code = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    created_by = Column(String(36), nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    finished_at = Column(DateTime, nullable=True)

class MusicBrief(Base):
    __tablename__ = "music_briefs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("production_projects.id"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    mood = Column(String(100), nullable=False)
    genre = Column(String(100), nullable=False)
    bpm = Column(Integer, nullable=True)
    vocal_language = Column(String(20), nullable=False, default="vi")
    duration_seconds = Column(Integer, nullable=False, default=60)
    prompt_text = Column(Text, nullable=False)
    created_by = Column(String(36), nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

class TimelineVersion(Base):
    __tablename__ = "timeline_versions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("production_projects.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    tracks_json = Column(Text, nullable=False, default="[]")
    is_locked = Column(Boolean, nullable=False, default=False)
    created_by = Column(String(36), nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_timeline_project_version"),
    )


class VoiceConsent(Base):
    __tablename__ = "voice_consents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    speaker_name = Column(String(255), nullable=False)
    consent_audio_asset_id = Column(String(36), ForeignKey("media_assets.id"), nullable=False)
    is_adult_verified = Column(Boolean, nullable=False, default=False)
    status = Column(String(50), nullable=False, default="ACTIVE") # ACTIVE, REVOKED
    signed_at = Column(DateTime, nullable=False, default=utc_now)

class MediaQCResult(Base):
    __tablename__ = "media_qc_results"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    asset_id = Column(String(36), ForeignKey("media_assets.id"), nullable=False, index=True)
    qc_type = Column(String(50), nullable=False) # AUDIO_LUFS, SAFE_ZONE, VIDEO_BITRATE, RIGHTS_CHECK
    passed = Column(Boolean, nullable=False, default=False)
    details_json = Column(Text, nullable=False, default="{}")
    reviewed_by = Column(String(36), nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)


# ==============================================================================
# PLATFORM CONFIGURATION ENTITIES (BAHA-AUTHZ-LLM-CONFIG)
# ==============================================================================

class PlatformLLMConfig(Base):
    """
    Cấu hình Cổng LLM dùng chung toàn nền tảng (Singleton).
    Chỉ duy nhất Quản Trị Viên Nền Tảng (Platform Owner) được quyền quản trị.
    Khóa API luôn được lưu trữ dưới dạng ciphertext đã mã hóa (Zero Plaintext Secrets).
    """
    __tablename__ = "platform_llm_configurations"

    id = Column(String(64), primary_key=True, default="default_platform_llm_config")
    is_enabled = Column(Boolean, nullable=False, default=False)
    base_url = Column(String(500), nullable=False, default="http://127.0.0.1:20128/v1")
    model = Column(String(255), nullable=False, default="gpt-4o-mini")
    api_key_ciphertext = Column(Text, nullable=True)
    key_fingerprint = Column(String(64), nullable=True)
    timeout_seconds = Column(Float, nullable=False, default=30.0)
    max_output_tokens = Column(Integer, nullable=False, default=1500)
    max_input_bytes = Column(Integer, nullable=False, default=20000)
    input_usd_per_1k_tokens = Column(Float, nullable=False, default=0.00015)
    output_usd_per_1k_tokens = Column(Float, nullable=False, default=0.00060)
    budget_units_per_usd = Column(Float, nullable=False, default=100.0)
    updated_by = Column(String(36), nullable=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
