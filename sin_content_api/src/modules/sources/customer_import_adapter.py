"""
Customer Import Adapter: Handles ingested customer datasets (JSON/CSV).
Account-only authorized import alternative for Offline MVP.
Strict validation: Isolates malformed records into quarantine; returns EMPTY on no match.
"""
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from .provider_protocol import (
    SourceProvider,
    ProviderCapabilities,
    ProviderCapabilityStatus,
    ProviderStatus,
    Platform,
    Precision,
    ProviderMetric,
    ProviderPost,
    ProviderComment,
    SearchQuery,
    Budget,
    AuthContext,
    ProviderError,
    Page,
)

class CustomerImportAdapter(SourceProvider):
    provider_id = "customer_import"
    platform = Platform.CUSTOMER_DATA

    def __init__(self):
        # In-memory store for imported records per workspace: workspace_id -> list of ProviderPost
        self._workspace_records: Dict[str, List[ProviderPost]] = {}
        # In-memory store for quarantined records per workspace: workspace_id -> list of dict
        self._quarantined_records: Dict[str, List[Dict[str, Any]]] = {}

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id=self.provider_id,
            platform=self.platform,
            search_content=ProviderCapabilityStatus.SUPPORTED,
            get_content=ProviderCapabilityStatus.SUPPORTED,
            get_comments=ProviderCapabilityStatus.SUPPORTED,
            list_profile_posts=ProviderCapabilityStatus.SUPPORTED,
            refresh_metrics=ProviderCapabilityStatus.UNSUPPORTED, # Static import cannot refresh live metrics
            live_status="AUTHORIZED_IMPORT", # Account-only authorized import alternative
            cost_per_request_usd=0.0,
            requires_oauth=False,
            rate_limit_rpm=300,
        )

    def import_batch(
        self, workspace_id: str, items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validates and imports a batch of records.
        Malformed records are isolated into quarantine.
        Returns: {
            "total": int,
            "valid_count": int,
            "quarantined_count": int,
            "status": ProviderStatus
        }
        """
        if workspace_id not in self._workspace_records:
            self._workspace_records[workspace_id] = []
        if workspace_id not in self._quarantined_records:
            self._quarantined_records[workspace_id] = []

        valid_items: List[ProviderPost] = []
        quarantined: List[Dict[str, Any]] = []

        for raw in items:
            # Check required fields
            external_id = raw.get("external_id") or raw.get("id")
            title = raw.get("title") or raw.get("caption") or raw.get("text_excerpt")
            
            # Validation failure condition (e.g. missing external_id or title, or invalid types)
            if not external_id or not title:
                quarantine_entry = {
                    "quarantine_id": str(uuid.uuid4()),
                    "workspace_id": workspace_id,
                    "provider_id": self.provider_id,
                    "raw_payload": raw,
                    "error_reason": "Missing required field: external_id or title/caption",
                    "quarantined_at": datetime.now(timezone.utc).isoformat(),
                }
                quarantined.append(quarantine_entry)
                self._quarantined_records[workspace_id].append(quarantine_entry)
                continue

            # P03-10: Process metrics preserving source precision
            metrics = []
            if "metrics" in raw and isinstance(raw["metrics"], list):
                for m in raw["metrics"]:
                    if isinstance(m, dict) and "metric_name" in m and "value" in m:
                        try:
                            # Khong nhan boolean hoac so am
                            if isinstance(m["value"], bool):
                                continue
                            val = int(m["value"])
                            if val >= 0:
                                prec_str = str(m.get("precision", "EXACT")).upper()
                                prec = Precision.ROUNDED if "ROUND" in prec_str else Precision.EXACT
                                metrics.append(
                                    ProviderMetric(
                                        metric_name=str(m["metric_name"]),
                                        value=val,
                                        precision=prec,
                                        source_reference=str(m.get("source_reference", "customer_export_file")),
                                    )
                                )
                        except (ValueError, TypeError):
                            pass
            elif "view_count" in raw and raw["view_count"] is not None:
                try:
                    if not isinstance(raw["view_count"], bool):
                        vc = int(raw["view_count"])
                        if vc >= 0:
                            metrics.append(
                                ProviderMetric(
                                    metric_name="VIEW_COUNT",
                                    value=vc,
                                    precision=Precision.EXACT,
                                    source_reference="customer_export_file",
                                )
                            )
                except (ValueError, TypeError):
                    pass

            # P03-02: Cam tu dong bia dat TikTok URL neu nguon khong co
            # P03-01: Bao toan co synthetic tu du lieu nguon thay vi ep cung False
            raw_synth = raw.get("synthetic", False)
            if isinstance(raw_synth, str):
                is_synth = raw_synth.lower() in ("true", "1", "yes")
            else:
                is_synth = bool(raw_synth)

            post = ProviderPost(
                external_id=str(external_id),
                canonical_url=raw.get("canonical_url") or "",
                title=str(title),
                text_excerpt=raw.get("text_excerpt") or str(title),
                published_at=raw.get("published_at"),
                language=raw.get("language", "vi"),
                metrics=metrics,
                synthetic=is_synth,
                quality_status="VALID",
                raw_payload=raw,
            )
            valid_items.append(post)
            self._workspace_records[workspace_id].append(post)


        if len(quarantined) == len(items) and len(items) > 0:
            status = ProviderStatus.INVALID_DATA
        elif len(quarantined) > 0:
            status = ProviderStatus.PARTIAL
        else:
            status = ProviderStatus.OK

        return {
            "total": len(items),
            "valid_count": len(valid_items),
            "quarantined_count": len(quarantined),
            "status": status,
        }

    def get_quarantined_records(self, workspace_id: str) -> List[Dict[str, Any]]:
        return self._quarantined_records.get(workspace_id, [])

    def search_content(
        self, query: SearchQuery, auth: AuthContext, budget: Budget
    ) -> Page[ProviderPost] | ProviderError:
        if not budget.can_spend(0.0):
            return ProviderError(
                error_code=ProviderStatus.BUDGET_EXCEEDED,
                provider_id=self.provider_id,
                request_id=str(uuid.uuid4()),
                retryable=False,
                message_safe="Budget limit reached for customer_import search",
            )
        budget.record_spend(0.0)

        records = self._workspace_records.get(auth.workspace_id, [])
        query_str = query.query.strip().lower()

        # If query is empty or no match, return EMPTY with 0 fake records
        if not query_str or not records:
            return Page(items=[], total_count=0, status=ProviderStatus.EMPTY)

        matched = [
            r for r in records
            if (r.title and query_str in r.title.lower()) or (r.text_excerpt and query_str in r.text_excerpt.lower())
        ]

        if not matched:
            return Page(items=[], total_count=0, status=ProviderStatus.EMPTY)

        return Page(items=matched[:query.limit], total_count=len(matched), status=ProviderStatus.OK)

    def get_content(
        self, external_ref: str, auth: AuthContext, budget: Budget
    ) -> ProviderPost | ProviderError:
        if not budget.can_spend(0.0):
            return ProviderError(
                error_code=ProviderStatus.BUDGET_EXCEEDED,
                provider_id=self.provider_id,
                request_id=str(uuid.uuid4()),
                retryable=False,
                message_safe="Budget limit reached",
            )
        budget.record_spend(0.0)

        records = self._workspace_records.get(auth.workspace_id, [])
        for r in records:
            if r.external_id == external_ref:
                return r

        return ProviderError(
            error_code=ProviderStatus.EMPTY,
            provider_id=self.provider_id,
            request_id=str(uuid.uuid4()),
            retryable=False,
            message_safe=f"Record {external_ref} not found in customer imports",
        )

    def get_comments(
        self, external_ref: str, cursor: Optional[str], auth: AuthContext, budget: Budget
    ) -> Page[ProviderComment] | ProviderError:
        # In this adapter, comments can be extracted from raw_payload if present
        records = self._workspace_records.get(auth.workspace_id, [])
        for r in records:
            if r.external_id == external_ref and r.raw_payload:
                raw_comments = r.raw_payload.get("comments", [])
                parsed = [
                    ProviderComment(
                        comment_id=str(c.get("id", f"c-{i}")),
                        post_external_id=external_ref,
                        text=str(c.get("text", "")),
                        author_id=c.get("author_id"),
                        like_count=c.get("like_count", 0),
                        synthetic=False,
                    )
                    for i, c in enumerate(raw_comments)
                    if isinstance(c, dict) and "text" in c
                ]
                if parsed:
                    return Page(items=parsed, total_count=len(parsed), status=ProviderStatus.OK)

        return Page(items=[], total_count=0, status=ProviderStatus.EMPTY)

    def list_profile_posts(
        self, profile_ref: str, cursor: Optional[str], auth: AuthContext, budget: Budget
    ) -> Page[ProviderPost] | ProviderError:
        records = self._workspace_records.get(auth.workspace_id, [])
        matched = [
            r for r in records
            if r.raw_payload and r.raw_payload.get("author_username", "").lower() == profile_ref.lower()
        ]
        if not matched:
            return Page(items=[], total_count=0, status=ProviderStatus.EMPTY)
        return Page(items=matched, total_count=len(matched), status=ProviderStatus.OK)

    def refresh_metrics(
        self, external_refs: List[str], auth: AuthContext, budget: Budget
    ) -> List[dict] | ProviderError:
        return ProviderError(
            error_code=ProviderStatus.UNAVAILABLE,
            provider_id=self.provider_id,
            request_id=str(uuid.uuid4()),
            retryable=False,
            message_safe="Customer import data does not support live metrics refresh.",
        )
