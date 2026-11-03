from enum import Enum
# Pydantic v2 Schemas phu hop voi CONTRACTS.md va JSON schemas (P01 -> P07)
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    environment: str = "offline"

class ReadyResponse(BaseModel):
    status: str = "ready"
    database_connected: bool = True
    offline_mode: bool = True
    version: str = "1.0.0"
    components: Optional[Dict[str, Any]] = None

class ErrorPayload(BaseModel):
    error_code: str
    message_safe: str
    correlation_id: str
    retryable: bool = False
    details: Optional[Dict[str, Any]] = None

class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=100)

class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    slug: str
    created_at: datetime

# P02: Schemas cho AudienceSegment va AllowedFact
class AudienceSegmentCreate(BaseModel):
    label: str = Field(..., min_length=3, description="Ten dinh danh phan khuc khan gia")
    contexts: List[str] = Field(default_factory=list, description="Boi canh hoac tinh huong su dung")
    needs: List[str] = Field(default_factory=list, description="Noi dau hoac nhu cau can giai quyet")
    disallowed_inferences: List[str] = Field(default_factory=list, description="Suy luan bi cam")
    awareness_stage: str = Field(default="PROBLEM_AWARE", description="Giai doan nhan thuc")

class AudienceSegmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    brief_version_id: str
    label: str
    contexts: List[str]
    needs: List[str]
    disallowed_inferences: List[str]
    awareness_stage: str
    created_at: datetime

class AllowedFactCreate(BaseModel):
    claim_text: str = Field(..., min_length=5, description="Noi dung tuyen bo su that ve san pham")
    fact_type: str = Field(default="PRODUCT_SPECS", description="Loai su that")
    source_citation: str = Field(..., min_length=3, description="Nguon trich dan chung minh (URL/Doc/SKU)")
    verification_status: str = Field(default="VERIFIED")

class AllowedFactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    brief_version_id: str
    claim_text: str
    fact_type: str
    source_citation: str
    verification_status: str
    created_at: datetime

# P02: BrandBrief validation chat che phuc vu Test T020
class BrandBriefCreate(BaseModel):
    brand_name: str = Field(..., min_length=2, max_length=255, description="Ten thuong hieu bat buoc >= 2 ky tu")
    objective: str = Field(..., min_length=5, description="Muc tieu kenh truyen thong bat buoc >= 5 ky tu")
    voice_description: str = Field(..., min_length=10, description="Mo ta giong dieu thuong hieu bat buoc >= 10 ky tu")
    current_audience: str = Field(..., min_length=5, description="Khan gia hien tai cua kenh")
    target_audience: str = Field(..., min_length=5, description="Khan gia muc tieu muon huong toi")
    topics_included: List[str] = Field(..., min_length=1, description="Chu de duoc phep (it nhat 1 chu de)")
    topics_excluded: List[str] = Field(..., min_length=1, description="Chu de bi cam - Brand safety exclusions (it nhat 1 chu de)")
    production_limits: List[str] = Field(default_factory=list)
    segments: Optional[List[AudienceSegmentCreate]] = Field(default_factory=list)
    allowed_facts: Optional[List[AllowedFactCreate]] = Field(default_factory=list)

class BrandBriefUpdate(BaseModel):
    brand_name: Optional[str] = Field(None, min_length=2)
    objective: Optional[str] = Field(None, min_length=5)
    voice_description: Optional[str] = Field(None, min_length=10)
    current_audience: Optional[str] = Field(None, min_length=5)
    target_audience: Optional[str] = Field(None, min_length=5)
    topics_included: Optional[List[str]] = None
    topics_excluded: Optional[List[str]] = None
    production_limits: Optional[List[str]] = None
    segments: Optional[List[AudienceSegmentCreate]] = None
    allowed_facts: Optional[List[AllowedFactCreate]] = None

    @field_validator("topics_excluded")
    def validate_topics_excluded(cls, v):
        if v is not None:
            cleaned = [item.strip() for item in v if isinstance(item, str) and item.strip()]
            if not cleaned:
                raise ValueError("TOPICS_EXCLUDED_CANNOT_BE_EMPTY")
            return cleaned
        return v

    @field_validator("topics_included")
    def validate_topics_included(cls, v):
        if v is not None:
            cleaned = [item.strip() for item in v if isinstance(item, str) and item.strip()]
            if not cleaned:
                raise ValueError("TOPICS_INCLUDED_CANNOT_BE_EMPTY")
            return cleaned
        return v


class BriefReviewRequest(BaseModel):
    action: Literal["APPROVE", "REQUEST_CHANGES"]
    notes: Optional[str] = None

class BrandBriefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspace_id: str
    version: int
    brand_name: str
    objective: str
    voice_description: str
    language: str
    current_audience: str
    target_audience: str
    topics_included: List[str]
    topics_excluded: List[str]
    production_limits: List[str]
    status: str
    approved_by_user_id: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    segments: List[AudienceSegmentOut] = Field(default_factory=list)
    allowed_facts: List[AllowedFactOut] = Field(default_factory=list)

class SourceRecordCreate(BaseModel):
    provider_id: str
    raw_external_id: str
    canonical_url: Optional[str] = None
    title: Optional[str] = None
    caption: Optional[str] = None
    synthetic: bool = False
    rights_basis: str = "customer_supplied"

class SourceRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspace_id: str
    provider_id: str
    raw_external_id: str
    canonical_url: Optional[str] = None
    title: Optional[str] = None
    synthetic: bool
    rights_basis: str
    created_at: datetime

class IdeaCardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspace_id: str
    brief_version_id: str
    title: str
    target_need: str
    hook: str
    content_angle: str = ""
    confidence_tier: str
    status: str
    overall_score: float
    evidence_excerpt_ids: List[str] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    duplicate_warning: Optional[str] = None
    rejection_reason: Optional[str] = None
    creator_id: Optional[str] = None
    version: int = 1
    review_reason: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    synthetic: bool
    created_at: datetime

# P06 Schemas: Understanding, Need Signals, Topic Clusters, ASR
class EvidenceExcerptCreate(BaseModel):
    source_record_id: str
    excerpt_text: str = Field(..., min_length=2)
    excerpt_type: Literal["CAPTION", "COMMENT", "TRANSCRIPT"] = "COMMENT"
    author_id: Optional[str] = None
    has_official_analytics: bool = False
    analytics_report_id: Optional[str] = None

class EvidenceExcerptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspace_id: str
    source_record_id: str
    excerpt_text: str
    excerpt_type: str
    author_id: Optional[str] = None
    observed_at: datetime
    is_sanitized: bool
    created_at: datetime

class NeedSignalCreate(BaseModel):
    evidence_excerpt_id: str
    intent_group: str
    need_category: str
    signal_text: str
    quote_text: str
    observed_vs_inferred: Literal["OBSERVED_DIRECT", "INFERRED_UNVERIFIED"] = "OBSERVED_DIRECT"
    confidence_score: float = 1.0
    demographic_inferences_json: Optional[str] = "[]"

class NeedSignalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspace_id: str
    evidence_excerpt_id: str
    intent_group: str
    need_category: str
    signal_text: str
    quote_text: str
    observed_vs_inferred: str
    confidence_score: float
    demographic_inferences_json: str
    created_at: datetime

class ExtractSignalsRequest(BaseModel):
    excerpt: EvidenceExcerptCreate

class ExtractSignalsResponse(BaseModel):
    excerpt: EvidenceExcerptOut
    signals: List[NeedSignalOut]
    prompt_injection_detected: bool = False
    warning_notes: Optional[str] = None

class TopicClusterSignalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    cluster_id: str
    need_signal_id: str
    need_signal: Optional[NeedSignalOut] = None

class TopicClusterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspace_id: str
    cluster_label: str
    intent_group: str
    need_category: str
    signal_count: int
    signals: List[TopicClusterSignalOut] = Field(default_factory=list)
    created_at: datetime

class ClusterRequest(BaseModel):
    enabled: bool = True
    intent_group: Optional[str] = None

class ClusterResponse(BaseModel):
    enabled: bool
    total_clusters: int
    clusters: List[TopicClusterOut]

class AsrStatusResponse(BaseModel):
    status: Literal["VERIFIED", "UNVERIFIED", "AUDIO_NOT_LICENSED"]
    offline_stub: bool = True
    licensed_audio_count: int = 0
    wer_percentage: Optional[float] = None
    terminology_accuracy: Optional[float] = None
    message: str

class AsrEvaluateRequest(BaseModel):
    reference_transcripts: List[str] = Field(..., min_length=1)
    hypothesis_transcripts: List[str] = Field(..., min_length=1)
    domain_terms: Optional[List[str]] = Field(default_factory=list)

class AsrEvaluateResponse(BaseModel):
    status: str
    wer_percentage: float
    domain_terminology_accuracy: float
    total_evaluated_samples: int
    details: Dict[str, Any]

# P07 Schemas: Explicit Scoring, Hybrid Search & Gold Precision Evaluation
class ScoringWeightsContract(BaseModel):
    audience_fit: float = 0.30          # 30%
    observed_evidence: float = 0.25     # 25%
    brand_objective: float = 0.20       # 20%
    content_uniqueness: float = 0.15    # 15%
    production_feasibility: float = 0.10 # 10%
    total: float = 1.00                 # 100%

class ScoringBreakdown(BaseModel):
    audience_fit_score: float
    observed_evidence_score: float
    brand_objective_score: float
    content_uniqueness_score: float
    production_feasibility_score: float
    overall_score: float
    veto_violation: bool
    veto_reason: Optional[str] = None
    growth_velocity: Optional[float] = None
    velocity_status: str
    velocity_confidence: str
    component_reasons: Dict[str, str] = Field(default_factory=dict)

class CandidateScoreRequest(BaseModel):
    brief_version_id: str
    candidate_id: str
    candidate_title: str
    content_excerpt: str
    evidence_tier: str = "LIMITED_SIGNAL" # EVIDENCE_BACKED, LIMITED_SIGNAL, HYPOTHESIS
    observed_vs_inferred: str = "OBSERVED_DIRECT"
    snapshots: Optional[List[Dict[str, Any]]] = None

class CandidateScoreResponse(BaseModel):
    candidate_id: str
    breakdown: ScoringBreakdown
    status: str

class HybridSearchRequest(BaseModel):
    brief_version_id: str
    query: Optional[str] = None
    intent_group: Optional[str] = None
    need_category: Optional[str] = None
    limit: int = Field(10, ge=1, le=100)
    provider_ids: Optional[List[str]] = None

class HybridSearchResultItem(BaseModel):
    id: str
    title: str
    excerpt: str
    hybrid_score: float
    scoring_breakdown: ScoringBreakdown
    source_url: Optional[str] = None
    evidence_tier: str

class HybridSearchResponse(BaseModel):
    total_found: int
    results: List[HybridSearchResultItem]

class GoldEvaluationResponse(BaseModel):
    brief_id: str
    brief_name: str
    total_candidates: int
    top_10_precision: float
    top_10_relevant_count: int
    top_10_veto_count: int
    meets_threshold: bool
    top_10_candidates: List[Dict[str, Any]]


# P08 Schemas: LLM Ideation, Citation Grounding, Verification & Duplicate Prevention
class CitationReference(BaseModel):
    excerpt_id: str
    quote_text: str
    source_url: Optional[str] = None
    author_id: Optional[str] = None
    observed_vs_inferred: str = "OBSERVED_DIRECT"
    confidence_score: float = 1.0

class IdeaCardCreate(BaseModel):
    brief_version_id: str
    title: str = Field(..., min_length=5, max_length=255)
    target_need: str = Field(..., min_length=5)
    hook: str = Field(..., min_length=5)
    content_angle: str = Field(..., min_length=5)
    confidence_tier: Literal["EVIDENCE_BACKED", "LIMITED_SIGNAL", "HYPOTHESIS"] = "EVIDENCE_BACKED"
    evidence_excerpt_ids: List[str] = Field(default_factory=list)
    citations: List[CitationReference] = Field(default_factory=list)
    overall_score: float = Field(0.0, ge=0.0, le=10.0)
    synthetic: bool = False
    allow_hypotheses: bool = False

class VerificationResult(BaseModel):
    is_valid: bool
    rejection_reason: Optional[str] = None
    rejection_code: Optional[str] = None # INVALID_CITATION_FABRICATION, PROHIBITED_TOPIC_VETO, INSUFFICIENT_EVIDENCE, DUPLICATE_EXISTS
    cited_excerpts_count: int = 0
    verified_excerpts_count: int = 0
    unverified_excerpts_count: int = 0
    fabricated_ids: List[str] = Field(default_factory=list)
    duplicate_warning: Optional[str] = None
    suggested_status: str

class IdeaCardVerifyRequest(BaseModel):
    idea_card: IdeaCardCreate
    workspace_id: Optional[str] = None

class IdeaCardVerifyResponse(BaseModel):
    verification: VerificationResult
    card_preview: Optional[Dict[str, Any]] = None

class IdeaGenerationRequest(BaseModel):
    brief_version_id: str
    num_ideas: int = Field(5, ge=1, le=20)
    allow_hypotheses: bool = False
    selected_need_categories: Optional[List[str]] = None
    candidate_ids: Optional[List[str]] = None
    max_cost_usd: float = 1.0

class IdeaGenerationResponse(BaseModel):
    brief_version_id: str
    total_generated: int
    confidence_tier_summary: Dict[str, int]
    ideas: List[IdeaCardOut]
    status: str # SUCCESS, INSUFFICIENT_EVIDENCE, SCHEMA_VALIDATION_ERROR, BUDGET_EXCEEDED
    message: Optional[str] = None
    generation_source: Optional[str] = 'offline_template'
    cost_units: Optional[float] = 0.0

class IdeaReviewRequest(BaseModel):
    action: Literal["APPROVE", "REJECT", "REQUEST_EVIDENCE", "REOPEN"]
    reviewer_notes: Optional[str] = None
    review_reason: Optional[str] = None
    expected_status: str = Field(..., description="Bắt buộc expected_status chống stale update (P10-02)")
    expected_version: int = Field(..., ge=1, description="Bắt buộc expected_version chống race condition (P10-02)")


# P09 Schemas: Script Drafting, Fact-Checking & Immutable Versioning
class ScriptBlock(BaseModel):
    block_type: Literal["HOOK", "SETUP", "VALUE", "PROOF", "CTA"]
    narration: str = Field(..., min_length=2)
    visual_cue: str = Field(..., min_length=2)
    duration_seconds: int = Field(..., ge=1, le=60)
    start_seconds: Optional[int] = None
    end_seconds: Optional[int] = None

class ClaimCheck(BaseModel):
    claim_text: str
    claim_type: Literal["QUANTITATIVE", "FEATURE", "PERFORMANCE", "PRICING", "POLICY"] = "QUANTITATIVE"
    allowed_fact_id: Optional[str] = None
    source_citation: Optional[str] = None
    verification_status: Literal["VERIFIED", "NEEDS_FACT_CHECK", "BLOCKING"] = "NEEDS_FACT_CHECK"
    notes: Optional[str] = None

class ScriptDraftCreate(BaseModel):
    idea_id: str
    title: str = Field(..., min_length=3, max_length=255)
    target_duration_seconds: int = Field(45, ge=15, le=180)
    hook_variants: List[str] = Field(..., min_length=2)
    blocks: List[ScriptBlock] = Field(..., min_length=3)
    claims: Optional[List[ClaimCheck]] = None

class ScriptDraftEditRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    target_duration_seconds: Optional[int] = Field(None, ge=15, le=180)
    hook_variants: Optional[List[str]] = Field(None, min_length=2)
    blocks: Optional[List[ScriptBlock]] = Field(None, min_length=3)
    claims: Optional[List[ClaimCheck]] = None
    editor_notes: Optional[str] = None

class ScriptDraftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspace_id: str
    idea_id: str
    created_by_user_id: Optional[str] = None
    version: int
    title: str
    target_duration_seconds: int
    actual_duration_seconds: int
    duration_tolerance_passed: bool
    hook_variants: List[str]
    blocks: List[ScriptBlock]
    claims: List[ClaimCheck]
    status: str # DRAFT, NEEDS_FACT_CHECK, READY_FOR_REVIEW, APPROVED, REJECTED, SUPERSEDED
    blocking_claims_count: int
    approved_by_user_id: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: datetime

class ScriptReviewRequest(BaseModel):
    action: Literal["APPROVE", "REJECT", "REQUEST_CHANGES"]
    reviewer_notes: Optional[str] = None


# P10 Schemas: Research Workbench & Reviewer Workflow
class ReviewAuditItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspace_id: str
    actor_id: str
    event_type: str
    details: Optional[str] = None
    created_at: datetime

class SourceRecordDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspace_id: str
    provider_id: str
    raw_external_id: str
    canonical_url: Optional[str] = None
    title: Optional[str] = None
    caption: Optional[str] = None
    synthetic: bool = False
    rights_basis: str = "customer_supplied"
    metric_status: Literal["VALID", "MISSING", "EXPIRED", "PARTIAL", "FUTURE_TIMESTAMP_INVALID"]
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    share_count: Optional[int] = None
    is_trending: Optional[bool] = None
    last_observed_at: Optional[datetime] = None
    created_at: datetime


# P11 Schemas: Owned Channel Feedback Loop & Trend Velocity (T110 - T113)
class VelocityCalculationRequest(BaseModel):
    source_record_id: str
    from_observation_id: str
    to_observation_id: str

class VelocityCalculationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    source_record_id: str
    from_observation_id: str
    to_observation_id: str
    metric_unit: str = "views"
    from_views: Optional[int] = None
    to_views: Optional[int] = None
    delta_views: Optional[int] = None
    delta_seconds: float
    delta_days: float
    velocity_views_per_day: Optional[float] = None
    growth_rate: Optional[float] = None
    rate_status: Literal["VALID", "NOT_AVAILABLE"] = "VALID"
    notes: Optional[str] = None

class CohortSummary(BaseModel):
    cohort: Literal["ORGANIC", "PAID"]
    total_posts: int
    total_views: int
    average_velocity_views_per_day: float
    average_engagement_rate: Optional[float] = None
    is_pooled: bool = False

class CohortAnalysisResponse(BaseModel):
    workspace_id: str
    filter_applied: str
    is_pooled_inference: bool = False # Luon luon la False theo T112
    organic_cohort: CohortSummary
    paid_cohort: CohortSummary
    warning: Optional[str] = None

class ChannelVerifyRequest(BaseModel):
    username_or_url: str

class ChannelConnectRequest(BaseModel):
    channel_id: str
    channel_name: str
    platform: str = "tiktok"
    oauth_scopes: List[str] = Field(default_factory=list)

class ChannelPerformanceResponse(BaseModel):
    channel_id: str
    channel_name: Optional[str] = None
    platform: str = "tiktok"
    status: Literal["CONNECTED", "FEATURE_UNAVAILABLE", "NOT_CONNECTED", "EXPIRED", "TOKEN_EXPIRED", "REVOKED"]
    has_metrics_scope: bool
    metrics: Optional[Dict[str, Any]] = None # Bat buoc None khi status != CONNECTED
    message: str

# P11 Published Content Links & Learning Signals Contracts
class PublishedContentLinkCreateRequest(BaseModel):
    script_draft_version_id: str
    platform: str = "tiktok"
    external_post_id: str
    external_post_url: str
    channel_id: Optional[str] = None
    is_paid: bool = False
    published_at: Optional[datetime] = None

class PublishedContentLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspace_id: str
    script_draft_version_id: str
    platform: str
    external_post_id: str
    external_post_url: str
    channel_id: Optional[str] = None
    is_paid: bool
    status: str
    published_at: Optional[datetime] = None
    created_at: datetime
    detached_at: Optional[datetime] = None

class PublishedContentLinkListResponse(BaseModel):
    workspace_id: str
    total: int
    items: List[PublishedContentLinkResponse]

class PerformanceSnapshotCreateRequest(BaseModel):
    published_content_link_id: str
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    share_count: Optional[int] = None
    watch_time_avg_seconds: Optional[float] = None
    completion_rate: Optional[float] = None
    snapshot_source: str = "TIKTOK_OFFICIAL_API"
    is_paid: bool = False
    observed_at: Optional[datetime] = None

class PerformanceSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspace_id: str
    published_content_link_id: str
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    share_count: Optional[int] = None
    watch_time_avg_seconds: Optional[float] = None
    completion_rate: Optional[float] = None
    snapshot_source: str
    is_paid: bool
    observed_at: datetime
    created_at: datetime

class LearningSignalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspace_id: str
    published_content_link_id: str
    signal_type: str
    score: float
    confidence: float
    formula_applied: str
    limitations_note: Optional[str] = None
    created_at: datetime

class LearningSignalListResponse(BaseModel):
    workspace_id: str
    total: int
    items: List[LearningSignalResponse]


class ExperimentSuggestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspace_id: str
    based_on_signal_id: str
    hypothesis: str
    suggested_action: str
    status: str
    created_at: datetime


class ExperimentSuggestionListResponse(BaseModel):
    workspace_id: str
    total: int
    items: List[ExperimentSuggestionResponse]


# ==========================================
# PHASE P12 CONTRACTS: SECURITY, RELIABILITY & STAGING EVALUATION
# ==========================================

class BudgetReserveRequest(BaseModel):
    workspace_id: str
    task_id: str
    idempotency_key: str
    action_type: str = "RESEARCH_RUN" # RESEARCH_RUN, IDEATION, SCRIPT_GEN, MEDIA_RENDER
    estimated_units: float = Field(gt=0, description="Estimated units to reserve")

class BudgetReserveResponse(BaseModel):
    status: Literal["RESERVED", "REFUSED_OVER_BUDGET", "IDEMPOTENT_HIT"]
    ledger_id: Optional[str] = None
    allocated_units: float
    available_units: float
    reserved_units: float
    message: str

class TaskExecuteRequest(BaseModel):
    workspace_id: str
    task_id: str
    idempotency_key: str
    action_type: str = "RESEARCH_RUN"
    estimated_units: float = Field(gt=0)
    simulate_timeout: bool = False
    max_retries: int = Field(default=3, le=5)

class TaskExecuteResponse(BaseModel):
    task_id: str
    idempotency_key: str
    status: Literal["COMPLETED", "FAILED", "RETRIED"]
    retry_count: int
    charged_units: float
    output_artifact_id: Optional[str] = None
    is_idempotent_replay: bool = False
    message: str

class ReconciliationRequest(BaseModel):
    workspace_id: str
    ledger_id: str
    vendor_reported_units: float = Field(ge=0)

class ReconciliationResponse(BaseModel):
    ledger_id: str
    actual_units: float
    vendor_reported_units: float
    discrepancy_delta: float
    discrepancy_alert: bool
    reconciled: bool
    message: str


# ==========================================
# PHASE P13 CONTRACTS: PRODUCTION CANARY AND ROLLBACK
# ==========================================

class CanaryDeployRequest(BaseModel):
    workspace_id: str
    tenant_name: str
    human_approval_id: str = Field(min_length=3, description="Mã văn bản phê duyệt của con người")
    signed_rights_reference: str = Field(min_length=3, description="Mã thỏa thuận bản quyền đã ký")
    traffic_percentage: float = Field(default=5.0, ge=1.0, le=50.0)

class CanaryDeployResponse(BaseModel):
    deployment_id: str
    workspace_id: str
    tenant_name: str
    status: Literal["CANARY_ACTIVE", "ROLLED_BACK", "GRADUATED"]
    traffic_percentage: float
    is_rollback_ready: bool
    message: str

class CanaryResearchRunRequest(BaseModel):
    deployment_id: str
    workspace_id: str
    brief_version_id: str
    estimated_quota_units: float = Field(default=1.0, gt=0)
    reviewer_notes: Optional[str] = None

class CanaryResearchRunResponse(BaseModel):
    run_id: str
    deployment_id: str
    workspace_id: str
    brief_version_id: str
    run_status: Literal["RUNNING", "COMPLETED", "ROLLED_BACK", "FAILED"]
    quota_cost_units: float
    real_source_ids: List[str]
    data_lineage: Dict[str, Any]
    review_output: Dict[str, Any]
    is_rollback_ready: bool
    message: str

class CanaryRollbackRequest(BaseModel):
    deployment_id: str
    workspace_id: str
    rollback_reason: str = Field(min_length=5, description="Lý do kích hoạt rollback")

class CanaryRollbackResponse(BaseModel):
    deployment_id: str
    status: Literal["ROLLED_BACK"]
    rollback_reason: str
    rolled_back_at: str
    message: str

class ProviderRevokeRequest(BaseModel):
    workspace_id: str
    provider_id: str
    revocation_reason: str = Field(min_length=5)

class ProviderAccessStatusResponse(BaseModel):
    workspace_id: str
    provider_id: str
    status: Literal["ACTIVE", "REVOKED", "UNAVAILABLE"]
    rights_basis: str
    no_bypass_enforced: bool
    message: str


# ==============================================================================
# P1 Production Workflow / BAHA AI Media Studio Schemas (MEDIA_P1)
# ==============================================================================

class MediaAssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspace_id: str
    project_id: Optional[str] = None
    storage_key: str
    sha256: str
    byte_size: int
    mime_detected: str
    duration_ms: Optional[int] = None
    source_product: str
    original_filename: Optional[str] = None
    license_record_id: Optional[str] = None
    approval_state: str
    parent_asset_id: Optional[str] = None
    created_by: str
    created_at: datetime
    url: Optional[str] = None

class MediaAssetUploadResponse(BaseModel):
    asset_id: str
    storage_key: str
    sha256: str
    byte_size: int
    mime_detected: str
    duration_ms: Optional[int] = None
    url: str
    status: str = "SUCCESS"

class AIGenerationJobCreate(BaseModel):
    project_id: Optional[str] = None
    asset_type: Literal["IMAGE", "VIDEO", "AUDIO", "MUSIC"]
    provider: Literal["GOOGLE_OFFICIAL", "FLOW_MUSIC_ASSISTED", "FAKE_PROVIDER"]
    provider_mode: Literal["OFFICIAL_API", "SUBSCRIPTION_ASSISTED", "TEST_MOCK"] = "OFFICIAL_API"
    model_id: str = Field(..., min_length=2)
    idempotency_key: str = Field(..., min_length=8, max_length=128)
    prompt_text: str = Field(..., min_length=1)
    estimated_cost: float = Field(0.0, ge=0.0)
    parameters: Dict[str, Any] = Field(default_factory=dict)

class AIGenerationJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspace_id: str
    project_id: Optional[str] = None
    asset_type: str
    provider: str
    provider_mode: str
    model_id: str
    idempotency_key: str
    state: str
    estimated_cost: float
    actual_cost: float
    cost_currency: str
    credits_source: str
    output_asset_ids: List[str] = Field(default_factory=list)
    retry_count: int
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_by: str
    created_at: datetime
    finished_at: Optional[datetime] = None

class ProductionProjectCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    script_id: Optional[str] = None
    workflow_type: Literal["AI_VIDEO", "AUTO_EDIT"] = "AI_VIDEO"

class ProductionProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspace_id: str
    title: str
    workflow_type: Literal["AI_VIDEO", "AUTO_EDIT"] = "AI_VIDEO"
    script_id: Optional[str] = None
    status: str
    created_by: str
    created_at: datetime

class MusicBriefCreate(BaseModel):
    project_id: Optional[str] = None
    title: str = Field(..., min_length=2, max_length=255)
    mood: str = Field(..., min_length=2)
    genre: str = Field(..., min_length=2)
    bpm: Optional[int] = Field(None, ge=40, le=240)
    vocal_language: str = "vi"
    duration_seconds: int = Field(60, ge=10, le=300)
    prompt_text: str = Field(..., min_length=5)

class MusicBriefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspace_id: str
    project_id: Optional[str] = None
    title: str
    mood: str
    genre: str
    bpm: Optional[int] = None
    vocal_language: str
    duration_seconds: int
    prompt_text: str
    created_by: str
    created_at: datetime

# ==============================================================================
# Timeline Contracts (M-P3)
# ==============================================================================

class TimelineClip(BaseModel):
    """Một phân cảnh trong timeline: anh tinh hoac clip video."""
    clip_id: str = Field(..., description="ID on dinh cua clip trong timeline; khong thay doi khi reorder")
    asset_id: str = Field(..., description="ID cua MediaAsset; bat buoc")
    media_type: Optional[str] = Field(None, description="image hoac video; server suy ra tu MIME asset")
    start_ms: int = Field(..., ge=0, description="Vi tri bat dau tren timeline (ms)")
    duration_ms: int = Field(..., gt=0, description="Thoi luong hien thi (ms); anh mac dinh 3000ms")
    trim_in_ms: int = Field(0, ge=0, description="Diem vao cua clip video (ms); 0 cho anh tinh")
    trim_out_ms: Optional[int] = Field(None, ge=0, description="Diem ra cua clip video (ms); None = cuoi clip")
    fit: str = Field("cover", pattern="^(cover|contain)$", description="cover hoac contain")

    @field_validator("fit")
    @classmethod
    def validate_fit(cls, v: str) -> str:
        if v not in ("cover", "contain"):
            raise ValueError("fit chi chap nhan 'cover' hoac 'contain'")
        return v

    @field_validator("trim_out_ms")
    @classmethod
    def validate_trim(cls, v: Optional[int], info) -> Optional[int]:
        if v is not None:
            trim_in = info.data.get("trim_in_ms", 0)
            if v <= trim_in:
                raise ValueError("trim_out_ms phai lon hon trim_in_ms")
        return v

class TimelineAudioTrack(BaseModel):
    """Track am thanh (voice hoac music)."""
    asset_id: str = Field(..., description="ID cua MediaAsset am thanh")
    start_ms: int = Field(0, ge=0, description="Vi tri bat dau tren timeline (ms)")
    duration_ms: Optional[int] = Field(None, gt=0, description="Thoi luong; None = toan bo asset")
    gain_db: float = Field(0.0, ge=-60.0, le=20.0, description="He so am luong (dB)")
    duck_music: bool = Field(False, description="Chỉ dành cho track music: duck khi co voice")

class TimelineCaption(BaseModel):
    """Phu de chu tren video."""
    text: str = Field(..., min_length=1, max_length=500)
    start_ms: int = Field(..., ge=0)
    end_ms: int = Field(..., gt=0)
    position_y_px: int = Field(500, ge=150, le=1600, description="Vi tri Y tren canvas 1080x1920, trong Safe Zone")
    font_size_px: int = Field(48, ge=24, le=120)

    @field_validator("end_ms")
    @classmethod
    def validate_time(cls, v: int, info) -> int:
        start = info.data.get("start_ms", 0)
        if v <= start:
            raise ValueError("end_ms phai lon hon start_ms")
        return v

class TimelineDocument(BaseModel):
    """
    Tai lieu timeline hoan chinh — hop dong M-P3.
    Moi thoi gian la so nguyen millisecond.
    """
    canvas_width_px: int = Field(1080, description="Do rong canvas (px)")
    canvas_height_px: int = Field(1920, description="Do cao canvas (px)")
    fps: int = Field(30, ge=24, le=60)
    clips: list[TimelineClip] = Field(default_factory=list)
    voice_track: Optional[TimelineAudioTrack] = None
    music_track: Optional[TimelineAudioTrack] = None
    captions: list[TimelineCaption] = Field(default_factory=list)

class TimelineVersionOut(BaseModel):
    """Ket qua tra ve sau khi luu hoac doc timeline."""
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    version: int
    is_locked: bool
    created_by: str
    created_at: datetime
    document: Optional[TimelineDocument] = None

class TimelinePutRequest(BaseModel):
    """Request body de luu timeline moi (PUT)."""
    expected_version: int = Field(..., ge=0, description="Version hien tai can biet; 0 = tao lan dau")
    document: TimelineDocument




# ==============================================================================
# Music Generation Contracts (GF04)
# ==============================================================================

class MusicProviderType(str, Enum):
    GOOGLE_OFFICIAL = "GOOGLE_OFFICIAL"
    FLOW_BROWSER_PILOT = "FLOW_BROWSER_PILOT"
    LOCAL_TEST_SYNTH = "LOCAL_TEST_SYNTH"


class MusicGenerationMode(str, Enum):
    CLIP_30S = "CLIP_30S"
    FULL_SONG = "FULL_SONG"
    PILOT_ASSISTED = "PILOT_ASSISTED"
    SYNTH_FIXTURE = "SYNTH_FIXTURE"


class MusicJobStatus(str, Enum):
    CREATED = "CREATED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    SUBMITTING = "SUBMITTING"
    RUNNING = "RUNNING"
    COLLECTING = "COLLECTING"
    VALIDATING = "VALIDATING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    NEEDS_RECONCILIATION = "NEEDS_RECONCILIATION"


class MusicGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=1000, description="Mô tả phong cách, giai điệu hoặc nội dung âm nhạc")
    genre: str = Field("Pop", max_length=50, description="Thể loại nhạc (Pop, Acoustic, Lo-Fi, Rock, Electronic...)")
    mood: str = Field("Upbeat", max_length=50, description="Tâm trạng bản nhạc (Upbeat, Relaxing, Energetic, Emotional...)")
    lyrics: Optional[str] = Field(None, max_length=2000, description="Lời bài hát kèm thẻ phân đoạn [Verse], [Chorus] nếu có")
    provider: MusicProviderType = Field(MusicProviderType.GOOGLE_OFFICIAL, description="Nhà cung cấp âm nhạc mục tiêu")
    mode: MusicGenerationMode = Field(MusicGenerationMode.CLIP_30S, description="Chế độ sinh nhạc")
    duration_sec: int = Field(30, ge=5, le=180, description="Thời lượng mong muốn (bắt buộc 30s với Lyria Clip)")
    project_id: Optional[str] = Field(None, description="ID dự án sản xuất liên kết")
    idempotency_key: str = Field(..., min_length=8, max_length=128, description="Khóa chống trùng lặp request")


class MusicQCReport(BaseModel):
    measured_i_lufs: float = Field(..., description="Âm lượng tích hợp đo đạc thực tế theo EBU R128 (LUFS)")
    measured_tp_dbtp: float = Field(..., description="Đỉnh cực đại thực tế đo đạc (dBTP)")
    measured_lra_lu: float = Field(..., description="Dải biến thiên âm lượng (LRA)")
    target_lufs: float = Field(-14.0, description="Mục tiêu chuẩn hóa TikTok (-14 LUFS)")
    passed: bool = Field(..., description="Đạt chuẩn kiểm định kỹ thuật")
    sample_rate_hz: int = Field(44100, description="Tần số lấy mẫu âm thanh")
    channels: int = Field(2, description="Số kênh âm thanh")


class MusicCapabilityItem(BaseModel):
    provider: MusicProviderType
    mode: MusicGenerationMode
    model_id: str
    enabled: bool
    blocked_reason: Optional[str] = None
    max_duration_sec: int
    cost_per_generation_usd: float
    requires_approval: bool
    observed_at: str


class MusicCapabilitiesResponse(BaseModel):
    workspace_id: str
    items: List[MusicCapabilityItem]
    default_provider: MusicProviderType
    pilot_enabled: bool


class MusicReviewRequest(BaseModel):
    decision: Literal["APPROVE", "REJECT"] = Field(..., description="Quyết định phê duyệt")
    review_notes: Optional[str] = Field(None, max_length=500, description="Ghi chú đánh giá")


# ==============================================================================
# M-P3 Timeline Contracts (P1 Production Workflow)
# ==============================================================================

class TimelineFitMode(str, Enum):
    COVER = "cover"
    CONTAIN = "contain"


class TimelineMediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


class TimelineClip(BaseModel):
    clip_id: str = Field(..., min_length=1, max_length=64, description="ID định danh duy nhất phân cảnh")
    asset_id: str = Field(..., min_length=1, description="ID MediaAsset")
    media_type: TimelineMediaType = Field(..., description="Loại media: image hoặc video")
    start_ms: int = Field(0, ge=0, description="Thời điểm bắt đầu phân cảnh trên timeline (ms)")
    duration_ms: int = Field(..., gt=0, description="Thời lượng phân cảnh (ms)")
    trim_in_ms: int = Field(0, ge=0, description="Điểm cắt đầu (ms)")
    trim_out_ms: int = Field(0, ge=0, description="Điểm cắt cuối (ms)")
    fit: TimelineFitMode = Field(TimelineFitMode.COVER, description="Chế độ khớp khung: cover | contain")
    audio_asset_id: Optional[str] = None
    audio_trim_in_ms: int = Field(0, ge=0)
    effect: Literal["none", "punch_in"] = "none"


class TimelineAudioTrack(BaseModel):
    asset_id: str = Field(..., min_length=1, description="ID MediaAsset âm thanh")
    start_ms: int = Field(0, ge=0, description="Thời điểm bắt đầu (ms)")
    duration_ms: Optional[int] = Field(None, ge=0, description="Thời lượng phát (ms)")
    gain_db: float = Field(0.0, description="Mức gain âm lượng (dB)")
    ducking_attenuation_db: Optional[float] = Field(None, description="Mức hạ âm khi ducking (dB)")


class TimelineCaptionWord(BaseModel):
    text: str = Field(..., min_length=1)
    start_ms: int = Field(..., ge=0)
    end_ms: int = Field(..., gt=0)


class TimelineCaption(BaseModel):
    caption_id: Optional[str] = Field(None, description="ID phụ đề")
    text: str = Field(..., min_length=1, description="Nội dung phụ đề")
    start_ms: int = Field(0, ge=0, description="Thời điểm bắt đầu (ms)")
    duration_ms: int = Field(..., gt=0, description="Thời lượng hiển thị (ms)")
    font_size: int = Field(26, ge=12, le=72, description="Cỡ chữ (px)")
    safe_zone: bool = Field(True, description="Tuân thủ Safe Zone TikTok")
    words: List[TimelineCaptionWord] = Field(default_factory=list, description="Mốc thời gian từng từ cho phụ đề karaoke")
    visual_type: Optional[Literal["callout"]] = None
    position_y_px: Optional[int] = Field(None, ge=150)


class TimelineOverlay(BaseModel):
    asset_id: str = Field(..., min_length=1)
    x: int = Field(0, ge=0)
    y: int = Field(0, ge=0)
    width: int = Field(320, gt=0)
    height: int = Field(480, gt=0)
    start_ms: int = Field(0, ge=0)
    duration_ms: int = Field(..., gt=0)


class KaraokeCaptionSettings(BaseModel):
    preset: Literal["bat_nhip", "to_sac", "hai_dong"] = "bat_nhip"
    font_size: Literal[42, 56, 70] = 56
    layout: Literal["center", "left", "two_line"] = "center"
    accent_color: Literal["champagne", "baha_blue", "coral"] = "champagne"
    outline: bool = True
    shadow: bool = True
    word_pop: bool = True


class TimelineDocument(BaseModel):
    width: int = Field(1080, description="Chiều rộng khung hình")
    height: int = Field(1920, description="Chiều cao khung hình")
    fps: int = Field(30, description="Tốc độ khung hình")
    clips: List[TimelineClip] = Field(default_factory=list, description="Danh sách phân cảnh theo thứ tự")
    voice_track: Optional[TimelineAudioTrack] = Field(None, description="Track giọng đọc")
    music_track: Optional[TimelineAudioTrack] = Field(None, description="Track nhạc nền")
    captions: List[TimelineCaption] = Field(default_factory=list, description="Danh sách phụ đề")
    overlays: List[TimelineOverlay] = Field(default_factory=list, description="Lớp phủ hình ảnh/video")
    caption_style: Literal["legacy", "vietsub_v1", "vietsub_karaoke_v2"] = "legacy"
    transition_seconds: float = Field(0.0, ge=0)
    karaoke_settings: KaraokeCaptionSettings = Field(default_factory=KaraokeCaptionSettings)

    @model_validator(mode="after")
    def validate_overlay_bounds(self):
        if any(
            overlay.x + overlay.width > self.width or overlay.y + overlay.height > self.height
            for overlay in self.overlays
        ):
            raise ValueError("Overlay vượt ngoài canvas timeline")
        return self


class TimelineVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    version: int
    timeline: TimelineDocument
    is_locked: bool
    created_by: str
    created_at: datetime


class TimelineSaveRequest(BaseModel):
    timeline: TimelineDocument
    expected_version: Optional[int] = Field(None, description="Phiên bản mong đợi để kiểm tra OCC conflict")

