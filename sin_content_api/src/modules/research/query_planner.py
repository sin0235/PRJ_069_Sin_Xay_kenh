"""
Deterministic Query Planner Engine (P05 / P05-02, P05-05, P05-06, P05-08, P05-09, P05-10).
Implements T050 (Brand Safety Exclusions) & T052 (Quota and Budget Caps).
Generates reproducible ResearchPlan matching research_request.schema.json.
"""
import json
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from src.models.entities import BrandBriefVersion
from .taxonomy import AUDIENCE_NEED_TAXONOMY, IntentGroup
from src.modules.sources.provider_registry import default_registry

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

class ResearchRequest(BaseModel):
    schema_version: str = "1.0"
    workspace_id: str
    brief_version_id: str
    intent_groups: List[IntentGroup] = Field(min_length=1)
    lookback_days: int = Field(default=30, ge=1, le=365)
    provider_ids: List[str] = Field(min_length=1)
    max_results: int = Field(default=100, ge=1, le=1000)
    max_cost_usd: float = Field(default=0.0, ge=0.0, le=10000.0)
    mode: str = "OFFLINE" # OFFLINE, APPROVED_LIVE
    synthetic: bool = False
    allow_hypotheses: bool = False
    query_seed: List[str] = Field(default_factory=list)
    negative_keywords: List[str] = Field(default_factory=list)
    request_id: Optional[str] = None

class QueryVariant(BaseModel):
    query_string: str
    intent_group: str
    target_segment: Optional[str] = None
    provider_id: str
    estimated_cost_usd: float = 0.0

class ResearchPlan(BaseModel):
    plan_id: str
    workspace_id: str
    brief_version_id: str
    intent_groups: List[str]
    query_variants: List[QueryVariant]
    negative_keywords: List[str] # Mandatory contains all topics_excluded (T050)
    source_quotas: Dict[str, int]
    max_results: int
    max_cost_usd: float
    estimated_cost_usd: float
    lookback_days: int = 30
    mode: str = "OFFLINE"
    synthetic: bool = False
    allow_hypotheses: bool = False
    created_at: str

PROHIBITED_PROVIDERS = {"mediacrawler"}

class QueryPlanner:
    def is_candidate_admissible(self, text: str, excluded_topics: List[str]) -> bool:
        """
        T050: Strict Brand Safety Check.
        Rejects any content candidate that contains prohibited topics.
        """
        if not text or not excluded_topics:
            return True
        text_lower = text.lower()
        for excluded in excluded_topics:
            if excluded.strip().lower() in text_lower:
                return False
        return True

    def get_provider_unit_cost(self, pid: str) -> float:
        """Lay chi phi moi request cua provider tu registry."""
        prov = default_registry.get_provider(pid)
        if not isinstance(prov, Exception) and hasattr(prov, "capabilities"):
            return prov.capabilities().cost_per_request_usd
        return 0.0

    def generate_plan(
        self,
        brief: BrandBriefVersion,
        request: ResearchRequest,
    ) -> ResearchPlan:
        """
        Generates deterministic query plan.
        Enforces T050 (exclusions), T052 (budget/quota caps), P05-02, P05-05, P05-08, P05-09.
        """
        plan_id = str(uuid.uuid4())

        # P05-05: Kiem tra provider_ids hop le va khong nam trong danh sach cam
        valid_pids = []
        for pid in request.provider_ids:
            if pid in PROHIBITED_PROVIDERS:
                raise ValueError(f"Provider '{pid}' bị cấm tuyệt đối theo chính sách bảo mật.")
            prov = default_registry.get_provider(pid)
            if isinstance(prov, Exception):
                raise ValueError(f"Provider '{pid}' không tồn tại hoặc chưa được đăng ký trong hệ thống.")
            valid_pids.append(pid)

        if not valid_pids:
            raise ValueError("Không có provider hợp lệ nào được chỉ định.")

        # Parse topics from brief
        included_topics = json.loads(brief.topics_included_json or "[]")
        excluded_topics = json.loads(brief.topics_excluded_json or "[]")
        
        # T050: Combine request negative keywords with brief's excluded topics (Brand Safety)
        combined_negatives = list(set(request.negative_keywords + excluded_topics))

        # P05-02 & P05-08: Tinh chi phi don vi theo tung provider
        provider_costs = {pid: self.get_provider_unit_cost(pid) for pid in valid_pids}

        # Candidate queries generation theo nhom intent (P05-09: phan bo can bang)
        variants_by_intent: Dict[str, List[QueryVariant]] = {}
        for intent in request.intent_groups:
            intent_val = intent.value if hasattr(intent, "value") else intent
            variants_by_intent[intent_val] = []

        # 1. Seed queries from request
        for seed in request.query_seed:
            if self.is_candidate_admissible(seed, combined_negatives):
                first_pid = valid_pids[0]
                target_intent = request.intent_groups[0].value if hasattr(request.intent_groups[0], "value") else request.intent_groups[0]
                variants_by_intent[target_intent].append(
                    QueryVariant(
                        query_string=seed,
                        intent_group=target_intent,
                        target_segment="SEED",
                        provider_id=first_pid,
                        estimated_cost_usd=provider_costs.get(first_pid, 0.0),
                    )
                )

        # 2. Combinatorial expansion from taxonomy templates and included topics
        primary_topic = included_topics[0] if included_topics else brief.brand_name
        
        for intent in request.intent_groups:
            intent_val = intent.value if hasattr(intent, "value") else intent
            tax_entry = AUDIENCE_NEED_TAXONOMY.get(intent_val, {})
            templates = tax_entry.get("templates", [])

            for tmpl in templates:
                q_text = tmpl.format(topic=primary_topic)
                
                # T050: Filter out any query variant that collides with prohibited topics
                if not self.is_candidate_admissible(q_text, combined_negatives):
                    continue

                for pid in valid_pids:
                    # P05-08: Tinh dung chi phi cua provider do (khong ep cost cua provider khac)
                    variants_by_intent[intent_val].append(
                        QueryVariant(
                            query_string=q_text,
                            intent_group=intent_val,
                            target_segment=(brief.target_audience or "")[:30],
                            provider_id=pid,
                            estimated_cost_usd=provider_costs.get(pid, 0.0),
                        )
                    )

        # P05-09: Round-robin / can bang cac nhom intent_group
        interleaved_variants: List[QueryVariant] = []
        max_variants_in_any = max((len(v_list) for v_list in variants_by_intent.values()), default=0)
        seen_keys = set()

        for idx in range(max_variants_in_any):
            for intent in request.intent_groups:
                intent_val = intent.value if hasattr(intent, "value") else intent
                v_list = variants_by_intent[intent_val]
                if idx < len(v_list):
                    v = v_list[idx]
                    key = (v.query_string.lower(), v.provider_id)
                    if key not in seen_keys:
                        seen_keys.add(key)
                        interleaved_variants.append(v)

        # P05-02 & T052: Enforce budget ceiling and quota
        final_variants: List[QueryVariant] = []
        accumulated_cost = 0.0

        for v in interleaved_variants:
            if len(final_variants) >= request.max_results:
                break
            
            unit_cost = v.estimated_cost_usd
            # Neu co gioi han chi phi (max_cost_usd > 0): kiem tra khong vuot qua ngan sach
            if request.max_cost_usd > 0.0:
                if accumulated_cost + unit_cost > request.max_cost_usd:
                    # Neu la provider mien phi (cost = 0) van co the them neu con cho trong quota
                    if unit_cost == 0.0 and len(final_variants) < request.max_results:
                        final_variants.append(v)
                    continue
            elif request.max_cost_usd == 0.0 and unit_cost > 0.0:
                # Ngan sach = 0 khong cho phep chay provider tinh phi
                continue

            final_variants.append(v)
            accumulated_cost += unit_cost

        # Compute source quotas
        source_quotas: Dict[str, int] = {}
        for v in final_variants:
            source_quotas[v.provider_id] = source_quotas.get(v.provider_id, 0) + 1

        return ResearchPlan(
            plan_id=plan_id,
            workspace_id=request.workspace_id,
            brief_version_id=request.brief_version_id,
            intent_groups=[(ig.value if hasattr(ig, "value") else ig) for ig in request.intent_groups],
            query_variants=final_variants,
            negative_keywords=combined_negatives,
            source_quotas=source_quotas,
            max_results=request.max_results,
            max_cost_usd=request.max_cost_usd,
            estimated_cost_usd=round(accumulated_cost, 4),
            lookback_days=request.lookback_days,
            mode=request.mode,
            synthetic=request.synthetic,
            allow_hypotheses=request.allow_hypotheses,
            created_at=utc_now_iso(),
        )

query_planner = QueryPlanner()
