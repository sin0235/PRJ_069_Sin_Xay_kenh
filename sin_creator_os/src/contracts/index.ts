// TypeScript interfaces tương thích với JSON Schemas và CONTRACTS.md (P01 -> P07)

export interface AudienceSegmentContract {
  id: string;
  brief_version_id: string;
  label: string;
  contexts: string[];
  needs: string[];
  disallowed_inferences: string[];
  awareness_stage: "UNAWARE" | "PROBLEM_AWARE" | "SOLUTION_AWARE" | "PRODUCT_AWARE" | "MOST_AWARE";
  created_at: string;
}

export interface AllowedFactContract {
  id: string;
  brief_version_id: string;
  claim_text: string;
  fact_type: "PRODUCT_SPECS" | "CLINICAL_TRIAL" | "PRICING" | "POLICY";
  source_citation: string;
  verification_status: "VERIFIED" | "EXEMPTED";
  created_at: string;
}

export interface BrandBriefVersionContract {
  id: string;
  workspace_id: string;
  version: number;
  brand_name: string;
  objective: string;
  voice_description: string;
  language: string;
  current_audience: string;
  target_audience: string;
  topics_included: string[];
  topics_excluded: string[];
  production_limits: string[];
  status: "DRAFT" | "IN_REVIEW" | "APPROVED" | "SUPERSEDED" | "CHANGES_REQUESTED";
  approved_by_user_id?: string;
  approved_at?: string;
  created_at: string;
  segments: AudienceSegmentContract[];
  allowed_facts: AllowedFactContract[];
}

export interface ResearchRequestContract {
  schema_version: string;
  workspace_id: string;
  brief_version_id: string;
  intent_groups: ("PROBLEMS" | "CONTEXTS" | "COMPARISONS" | "OBJECTIONS" | "QUESTIONS" | "TRENDS")[];
  lookback_days: number;
  provider_ids: string[];
  max_results: number;
  max_cost_usd: number;
  mode: "OFFLINE" | "APPROVED_LIVE";
  synthetic: boolean;
  allow_hypotheses: boolean;
  query_seed?: string[];
  negative_keywords?: string[];
}

export interface QueryVariantContract {
  query_string: string;
  intent_group: string;
  target_segment?: string;
  provider_id: string;
  estimated_cost_usd: number;
}

export interface ResearchPlanContract {
  plan_id: string;
  workspace_id: string;
  brief_version_id: string;
  intent_groups: string[];
  query_variants: QueryVariantContract[];
  negative_keywords: string[];
  source_quotas: Record<string, number>;
  max_results: number;
  max_cost_usd: number;
  estimated_cost_usd: number;
  created_at: string;
}

export interface GoldCandidateContract {
  id: string;
  brief_id: string;
  brief_name: string;
  candidate_title: string;
  content_excerpt: string;
  source_url: string;
  evidence_tier: string;
  reviewer_1_label: "RELEVANT" | "BORDERLINE" | "IRRELEVANT";
  reviewer_1_score: number;
  reviewer_2_label: "RELEVANT" | "BORDERLINE" | "IRRELEVANT";
  reviewer_2_score: number;
  adjudication_label: "RELEVANT" | "BORDERLINE" | "IRRELEVANT";
  final_score: number;
  adjudication_reason: string;
  has_veto_violation: boolean;
}

export interface GoldSummaryContract {
  brief_id: string;
  brief_name: string;
  total_candidates: number;
  relevant_count: number;
  borderline_count: number;
  irrelevant_count: number;
  veto_count: number;
  relevance_rate: number;
}

export interface ProviderMetricContract {
  metric_name: "VIEW_COUNT" | "LIKE_COUNT" | "COMMENT_COUNT" | "SHARE_COUNT" | "FOLLOWER_COUNT";
  value: number;
  observed_at: string;
  precision: "EXACT" | "ROUNDED" | "ESTIMATED";
  source_reference: string;
}

export interface ProviderPostContract {
  external_id: string;
  canonical_url?: string;
  title?: string;
  text_excerpt?: string;
  published_at?: string;
  observed_at: string;
  language?: string;
  metrics: ProviderMetricContract[];
  synthetic: boolean;
  quality_status: "VALID" | "PARTIAL" | "QUARANTINED";
}

export interface SourceObservationContract {
  id: string;
  workspace_id: string;
  source_record_id: string;
  observation_id: string;
  provider_id: string;
  observed_at: string;
  rights_basis: string;
  retention_days: number;
  is_purged: boolean;
}

export interface SourceRecordContract {
  id: string;
  workspace_id: string;
  provider_id: string;
  raw_external_id: string;
  canonical_url?: string;
  title?: string;
  caption?: string;
  synthetic: boolean;
  rights_basis: string;
  observed_at: string;
  is_purged: boolean;
  purged_at?: string;
}

// P06: Understanding, Need Signals, Clusters, ASR
export interface EvidenceExcerptContract {
  id: string;
  workspace_id: string;
  source_record_id: string;
  excerpt_text: string;
  excerpt_type: "CAPTION" | "COMMENT" | "TRANSCRIPT";
  author_id?: string;
  observed_at: string;
  is_sanitized: boolean;
  created_at: string;
}

export interface NeedSignalContract {
  id: string;
  workspace_id: string;
  evidence_excerpt_id: string;
  intent_group: "PROBLEMS" | "CONTEXTS" | "COMPARISONS" | "OBJECTIONS" | "QUESTIONS" | "TRENDS";
  need_category: string;
  signal_text: string;
  quote_text: string;
  observed_vs_inferred: "OBSERVED_DIRECT" | "INFERRED_UNVERIFIED";
  confidence_score: number;
  demographic_inferences_json: string;
  created_at: string;
}

export interface TopicClusterSignalContract {
  id: string;
  cluster_id: string;
  need_signal_id: string;
  need_signal?: NeedSignalContract;
}

export interface TopicClusterContract {
  id: string;
  workspace_id: string;
  cluster_label: string;
  intent_group: string;
  need_category: string;
  signal_count: number;
  signals: TopicClusterSignalContract[];
  created_at: string;
}

export interface AsrStatusContract {
  status: "VERIFIED" | "UNVERIFIED" | "AUDIO_NOT_LICENSED";
  offline_stub: boolean;
  licensed_audio_count: number;
  wer_percentage?: number;
  terminology_accuracy?: number;
  message: string;
}

// P07: Explicit Scoring & Hybrid Retrieval
export interface ScoringWeightsContract {
  audience_fit: number;          // 0.30
  observed_evidence: number;     // 0.25
  brand_objective: number;       // 0.20
  content_uniqueness: number;    // 0.15
  production_feasibility: number;// 0.10
  total: number;                 // 1.00
}

export interface ScoringBreakdownContract {
  audience_fit_score: number;
  observed_evidence_score: number;
  brand_objective_score: number;
  content_uniqueness_score: number;
  production_feasibility_score: number;
  overall_score: number;
  veto_violation: boolean;
  veto_reason?: string;
  growth_velocity?: number;
  velocity_status: "NOT_AVAILABLE" | "CALCULATED" | "UNVERIFIED_NULL_METRIC";
  velocity_confidence: "UNVERIFIED_SINGLE_SNAPSHOT" | "VERIFIED_MULTI_SNAPSHOT";
}

export interface HybridSearchResultItemContract {
  id: string;
  title: string;
  excerpt: string;
  hybrid_score: number;
  scoring_breakdown: ScoringBreakdownContract;
  source_url?: string;
  evidence_tier: string;
}

export interface HybridSearchResponseContract {
  total_found: number;
  results: HybridSearchResultItemContract[];
}

export interface GoldEvaluationResponseContract {
  brief_id: string;
  brief_name: string;
  total_candidates: number;
  top_10_precision: number;
  top_10_relevant_count: number;
  top_10_veto_count: number;
  meets_threshold: boolean;
  top_10_candidates: {
    id: string;
    title: string;
    overall_score: number;
    adjudication_label: string;
    has_veto_violation: boolean;
  }[];
}

export interface CitationReferenceContract {
  excerpt_id: string;
  quote_text: string;
  source_url?: string;
  author_id?: string;
  observed_vs_inferred: "OBSERVED_DIRECT" | "INFERRED_UNVERIFIED";
  confidence_score: number;
}

export interface IdeaCardContract {
  id: string;
  workspace_id: string;
  brief_version_id: string;
  title: string;
  target_need: string;
  hook: string;
  content_angle: string;
  confidence_tier: "EVIDENCE_BACKED" | "LIMITED_SIGNAL" | "HYPOTHESIS";
  status: "DRAFT" | "NEEDS_EVIDENCE" | "READY_FOR_REVIEW" | "APPROVED" | "REJECTED";
  overall_score: number;
  evidence_excerpt_ids: string[];
  duplicate_warning?: string;
  rejection_reason?: string;
  creator_id?: string;
  version?: number;
  review_reason?: string;
  reviewed_by?: string;
  reviewed_at?: string;
  synthetic: boolean;
  created_at: string;
}

export interface IdeaCardCreateContract {
  brief_version_id: string;
  title: string;
  target_need: string;
  hook: string;
  content_angle: string;
  confidence_tier: "EVIDENCE_BACKED" | "LIMITED_SIGNAL" | "HYPOTHESIS";
  evidence_excerpt_ids: string[];
  citations?: CitationReferenceContract[];
  overall_score?: number;
  synthetic?: boolean;
  allow_hypotheses?: boolean;
}

export interface VerificationResultContract {
  is_valid: boolean;
  rejection_reason?: string;
  rejection_code?: "INVALID_CITATION_FABRICATION" | "PROHIBITED_TOPIC_VETO" | "INSUFFICIENT_EVIDENCE" | "DUPLICATE_EXISTS";
  cited_excerpts_count: number;
  verified_excerpts_count: number;
  unverified_excerpts_count: number;
  fabricated_ids: string[];
  duplicate_warning?: string;
  suggested_status: string;
}

export interface IdeaCardVerifyResponseContract {
  verification: VerificationResultContract;
  card_preview?: Record<string, any>;
}

export interface IdeaGenerationRequestContract {
  brief_version_id: string;
  num_ideas?: number;
  allow_hypotheses?: boolean;
  selected_need_categories?: string[];
  candidate_ids?: string[];
  max_cost_usd?: number;
}

export interface IdeaGenerationResponseContract {
  brief_version_id: string;
  total_generated: number;
  confidence_tier_summary: Record<string, number>;
  ideas: IdeaCardContract[];
  status: "SUCCESS" | "INSUFFICIENT_EVIDENCE" | "SCHEMA_VALIDATION_ERROR" | "BUDGET_EXCEEDED";
  message?: string;
}

export interface IdeaReviewRequestContract {
  action: "APPROVE" | "REJECT" | "REQUEST_EVIDENCE" | "REOPEN";
  expected_version: number;
  expected_status: string;
  review_reason: string;
  reviewer_notes?: string;
}

export interface ScriptBlockContract {
  block_type: "HOOK" | "SETUP" | "VALUE" | "PROOF" | "CTA";
  narration: string;
  visual_cue: string;
  duration_seconds: number;
  start_seconds?: number;
  end_seconds?: number;
}

export interface ClaimCheckContract {
  claim_text: string;
  claim_type: "QUANTITATIVE" | "FEATURE" | "PERFORMANCE" | "PRICING" | "POLICY";
  allowed_fact_id?: string;
  source_citation?: string;
  verification_status: "VERIFIED" | "NEEDS_FACT_CHECK" | "BLOCKING";
  notes?: string;
}

export interface ScriptDraftContract {
  id: string;
  workspace_id: string;
  idea_id: string;
  version: number;
  title: string;
  target_duration_seconds: number;
  actual_duration_seconds: number;
  duration_tolerance_passed: boolean;
  hook_variants: string[];
  blocks: ScriptBlockContract[];
  claims: ClaimCheckContract[];
  status: "DRAFT" | "NEEDS_FACT_CHECK" | "READY_FOR_REVIEW" | "APPROVED" | "REJECTED" | "SUPERSEDED";
  blocking_claims_count: number;
  approved_by_user_id?: string;
  approved_at?: string;
  rejection_reason?: string;
  created_at: string;
}

export interface ScriptDraftCreateContract {
  idea_id: string;
  title: string;
  target_duration_seconds: number;
  hook_variants: string[];
  blocks: ScriptBlockContract[];
  claims?: ClaimCheckContract[];
}

export interface ScriptDraftEditRequestContract {
  title?: string;
  target_duration_seconds?: number;
  hook_variants?: string[];
  blocks?: ScriptBlockContract[];
  claims?: ClaimCheckContract[];
  editor_notes?: string;
}

export interface ScriptReviewRequestContract {
  action: "APPROVE" | "REJECT" | "REQUEST_CHANGES";
  reviewer_notes?: string;
}


// P10 Contracts: Research Workbench & Reviewer Workflow
export interface ReviewAuditItemContract {
  id: string;
  workspace_id: string;
  actor_id: string;
  event_type: string;
  details?: string | null;
  created_at: string;
}

export interface SourceRecordDetailContract extends SourceRecordContract {
  metric_status: "VALID" | "MISSING" | "EXPIRED";
  view_count: number | null;
  like_count?: number | null;
  comment_count?: number | null;
  share_count?: number | null;
  is_trending: boolean | null;
  last_observed_at?: string | null;
}


// P11 Contracts: Owned Channel Feedback Loop & Trend Velocity (T110 - T113)
export interface VelocityCalculationRequestContract {
  source_record_id: string;
  from_observation_id: string;
  to_observation_id: string;
}

export interface VelocityCalculationResponseContract {
  source_record_id: string;
  from_observation_id: string;
  to_observation_id: string;
  metric_unit: string;
  from_views: number;
  to_views: number;
  delta_views: number;
  delta_seconds: number;
  delta_days: number;
  velocity_views_per_day: number;
  growth_rate?: number | null;
  rate_status: "VALID" | "NOT_AVAILABLE";
  notes?: string | null;
}

export interface CohortSummaryContract {
  cohort: "ORGANIC" | "PAID";
  total_posts: number;
  total_views: number;
  average_velocity_views_per_day: number;
  average_engagement_rate?: number | null;
  is_pooled: boolean;
}

export interface CohortAnalysisResponseContract {
  workspace_id: string;
  filter_applied: string;
  is_pooled_inference: boolean;
  organic_cohort: CohortSummaryContract;
  paid_cohort: CohortSummaryContract;
  warning?: string | null;
}

export interface ChannelPerformanceResponseContract {
  channel_id: string;
  channel_name?: string | null;
  platform: string;
  status: "CONNECTED" | "FEATURE_UNAVAILABLE" | "NOT_CONNECTED" | "EXPIRED";
  has_metrics_scope: boolean;
  metrics?: Record<string, any> | null;
  message: string;
}


// ==========================================
// PHASE P12 CONTRACTS: SECURITY, RELIABILITY & STAGING EVALUATION
// ==========================================

export interface BudgetReserveRequestContract {
  workspace_id: string;
  task_id: string;
  idempotency_key: string;
  action_type: string;
  estimated_units: number;
}

export interface BudgetReserveResponseContract {
  status: "RESERVED" | "REFUSED_OVER_BUDGET" | "IDEMPOTENT_HIT";
  ledger_id?: string | null;
  allocated_units: number;
  available_units: number;
  reserved_units: number;
  message: string;
}

export interface TaskExecuteRequestContract {
  workspace_id: string;
  task_id: string;
  idempotency_key: string;
  action_type: string;
  estimated_units: number;
  simulate_timeout?: boolean;
  max_retries?: number;
}

export interface TaskExecuteResponseContract {
  task_id: string;
  idempotency_key: string;
  status: "COMPLETED" | "FAILED" | "RETRIED";
  retry_count: number;
  charged_units: number;
  output_artifact_id?: string | null;
  is_idempotent_replay: boolean;
  message: string;
}

export interface ReconciliationRequestContract {
  workspace_id: string;
  ledger_id: string;
  vendor_reported_units: number;
}

export interface ReconciliationResponseContract {
  ledger_id: string;
  actual_units: number;
  vendor_reported_units: number;
  discrepancy_delta: number;
  discrepancy_alert: boolean;
  reconciled: boolean;
  message: string;
}


// ==========================================
// PHASE P13 CONTRACTS: PRODUCTION CANARY AND ROLLBACK
// ==========================================

export interface CanaryDeployRequestContract {
  workspace_id: string;
  tenant_name: string;
  human_approval_id: string;
  signed_rights_reference: string;
  traffic_percentage?: number;
}

export interface CanaryDeployResponseContract {
  deployment_id: string;
  workspace_id: string;
  tenant_name: string;
  status: "CANARY_ACTIVE" | "ROLLED_BACK" | "GRADUATED";
  traffic_percentage: number;
  is_rollback_ready: boolean;
  message: string;
}

export interface CanaryResearchRunRequestContract {
  deployment_id: string;
  workspace_id: string;
  brief_version_id: string;
  estimated_quota_units?: number;
  reviewer_notes?: string | null;
}

export interface CanaryResearchRunResponseContract {
  run_id: string;
  deployment_id: string;
  workspace_id: string;
  brief_version_id: string;
  run_status: "RUNNING" | "COMPLETED" | "ROLLED_BACK" | "FAILED";
  quota_cost_units: number;
  real_source_ids: string[];
  data_lineage: Record<string, any>;
  review_output: Record<string, any>;
  is_rollback_ready: boolean;
  message: string;
}

export interface CanaryRollbackRequestContract {
  deployment_id: string;
  workspace_id: string;
  rollback_reason: string;
}

export interface CanaryRollbackResponseContract {
  deployment_id: string;
  status: "ROLLED_BACK";
  rollback_reason: string;
  rolled_back_at: string;
  message: string;
}

export interface ProviderRevokeRequestContract {
  workspace_id: string;
  provider_id: string;
  revocation_reason: string;
}

export interface ProviderAccessStatusResponseContract {
  workspace_id: string;
  provider_id: string;
  status: "ACTIVE" | "REVOKED" | "UNAVAILABLE";
  rights_basis: string;
  no_bypass_enforced: boolean;
  message: string;
}

// ==============================================================================
// PHASE P11 & P12 CONTRACTS: PUBLISHED CONTENT LINKS, LEARNING SIGNALS & BUDGET
// ==============================================================================

export interface PublishedContentLinkCreateRequestContract {
  script_draft_version_id: string;
  platform?: string;
  external_post_id: string;
  external_post_url: string;
  channel_id?: string;
  is_paid?: boolean;
  published_at?: string;
}

export interface PublishedContentLinkContract {
  id: string;
  workspace_id: string;
  script_draft_version_id: string;
  platform: string;
  external_post_id: string;
  external_post_url: string;
  channel_id?: string;
  is_paid: boolean;
  status: "ACTIVE" | "DETACHED" | "PURGED";
  published_at?: string;
  created_at: string;
  detached_at?: string;
}

export interface PublishedContentLinkListResponseContract {
  workspace_id: string;
  total: number;
  items: PublishedContentLinkContract[];
}

export interface PerformanceSnapshotCreateRequestContract {
  published_content_link_id: string;
  view_count?: number | null;
  like_count?: number | null;
  comment_count?: number | null;
  share_count?: number | null;
  watch_time_avg_seconds?: number | null;
  completion_rate?: number | null;
  snapshot_source?: string;
  is_paid?: boolean;
  observed_at?: string;
}

export interface PerformanceSnapshotContract {
  id: string;
  workspace_id: string;
  published_content_link_id: string;
  view_count?: number | null;
  like_count?: number | null;
  comment_count?: number | null;
  share_count?: number | null;
  watch_time_avg_seconds?: number | null;
  completion_rate?: number | null;
  snapshot_source: string;
  is_paid: boolean;
  observed_at: string;
  created_at: string;
}

export interface LearningSignalContract {
  id: string;
  workspace_id: string;
  published_content_link_id: string;
  signal_type: string;
  score: number;
  confidence: number;
  formula_applied: string;
  limitations_note?: string;
  insight_text?: string;
  created_at: string;
}

export interface LearningSignalListResponseContract {
  workspace_id: string;
  total: number;
  items: LearningSignalContract[];
}

export interface ExperimentSuggestionContract {
  id: string;
  workspace_id: string;
  based_on_signal_id: string;
  hypothesis: string;
  suggested_action: string;
  status: "PROPOSED" | "ACCEPTED" | "REJECTED" | "EXECUTED";
  created_at: string;
}

export interface ExperimentSuggestionListResponseContract {
  workspace_id: string;
  total: number;
  items: ExperimentSuggestionContract[];
}

export interface WorkspaceBudgetContract {
  id: string;
  workspace_id: string;
  allocated_units: number;
  reserved_units: number;
  spent_units: number;
  hard_limit_units: number;
  alert_threshold_percent: number;
  updated_at: string;
}

export interface CostLedgerContract {
  id: string;
  workspace_id: string;
  actor_user_id: string;
  action_key: string;
  cost_usd: number;
  model_or_provider?: string;
  created_at: string;
}

