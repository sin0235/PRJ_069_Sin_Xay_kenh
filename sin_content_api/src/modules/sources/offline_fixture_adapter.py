"""
Offline Fixture Adapter for testing and synthetic validation.
Strict rule: synthetic is ALWAYS True; provider_id is ALWAYS 'test_fixture'.
Never claims live status or real-world validity.
"""
import uuid
from typing import List, Optional
from datetime import datetime, timezone

from .provider_protocol import (
    SourceProvider,
    ProviderCapabilities,
    ProviderCapabilityStatus,
    ProviderStatus,
    Platform,
    RetrievalMethod,
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

class OfflineFixtureAdapter(SourceProvider):
    provider_id = "test_fixture"
    platform = Platform.TIKTOK

    def __init__(self):
        # Configurable fault injection for testing error scenarios
        self.simulated_fault: Optional[str] = None
        self.simulated_retry_after: int = 5

    def set_simulated_fault(self, fault: Optional[str], retry_after: int = 5):
        """Simulate upstream fault: '401', '403', '429', '500', 'malformed'"""
        self.simulated_fault = fault
        self.simulated_retry_after = retry_after

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id=self.provider_id,
            platform=self.platform,
            search_content=ProviderCapabilityStatus.SUPPORTED,
            get_content=ProviderCapabilityStatus.SUPPORTED,
            get_comments=ProviderCapabilityStatus.SUPPORTED,
            list_profile_posts=ProviderCapabilityStatus.SUPPORTED,
            refresh_metrics=ProviderCapabilityStatus.SUPPORTED,
            live_status="UNVERIFIED", # Synthetic fixture only, never live!
            cost_per_request_usd=0.0,
            requires_oauth=False,
            rate_limit_rpm=120,
        )

    def _check_budget(self, budget: Budget) -> Optional[ProviderError]:
        if not budget.can_spend(0.0):
            return ProviderError(
                error_code=ProviderStatus.BUDGET_EXCEEDED,
                provider_id=self.provider_id,
                request_id=str(uuid.uuid4()),
                retryable=False,
                message_safe="Budget limit exceeded: max requests or cost reached",
            )
        budget.record_spend(0.0)
        return None

    def _handle_simulated_fault(self) -> Optional[ProviderError]:
        if self.simulated_fault in ["401", "AUTH_FAILED"]:
            return ProviderError(
                error_code=ProviderStatus.AUTH_FAILED,
                provider_id=self.provider_id,
                request_id=str(uuid.uuid4()),
                retryable=False,
                message_safe="Simulated 401 Unauthorized: Invalid credentials",
            )
        elif self.simulated_fault in ["403", "FORBIDDEN", "CAPTCHA"]:
            return ProviderError(
                error_code=ProviderStatus.FORBIDDEN,
                provider_id=self.provider_id,
                request_id=str(uuid.uuid4()),
                retryable=False,
                message_safe="Simulated 403 Forbidden / Captcha detected. No bypass permitted.",
            )
        elif self.simulated_fault in ["429", "RATE_LIMITED"]:
            return ProviderError(
                error_code=ProviderStatus.RATE_LIMITED,
                provider_id=self.provider_id,
                request_id=str(uuid.uuid4()),
                retryable=True,
                retry_after_seconds=self.simulated_retry_after,
                message_safe=f"Simulated 429 Too Many Requests. Bounded backoff retry after {self.simulated_retry_after}s.",
            )
        elif self.simulated_fault in ["500", "UNAVAILABLE"]:
            return ProviderError(
                error_code=ProviderStatus.UNAVAILABLE,
                provider_id=self.provider_id,
                request_id=str(uuid.uuid4()),
                retryable=True,
                message_safe="Simulated 500 Server Error: Provider service unavailable",
            )
        return None

    def search_content(
        self, query: SearchQuery, auth: AuthContext, budget: Budget
    ) -> Page[ProviderPost] | ProviderError:
        budget_err = self._check_budget(budget)
        if budget_err:
            return budget_err

        fault_err = self._handle_simulated_fault()
        if fault_err:
            return fault_err

        query_str = query.query.strip().lower()

        # T030: If search query requests empty or nonexistent term, return EMPTY with 0 fake records
        if not query_str or any(term in query_str for term in ["empty", "nonexistent", "zero_results"]):
            return Page(
                items=[],
                total_count=0,
                status=ProviderStatus.EMPTY,
                partial_quarantined_count=0,
            )

        # T033: Handle simulated malformed payload
        if self.simulated_fault == "malformed":
            return Page(
                items=[
                    ProviderPost(
                        external_id="fixture-post-valid-01",
                        canonical_url="https://example.invalid/fixture-valid",
                        title="Valid fixture post",
                        text_excerpt="Text snippet",
                        synthetic=True,
                        quality_status="VALID",
                    )
                ],
                total_count=1,
                status=ProviderStatus.PARTIAL,
                partial_quarantined_count=2, # 2 malformed records isolated
            )

        # Standard synthetic fixtures (ALWAYS synthetic=True)
        items = [
            ProviderPost(
                external_id="synthetic-tiktok-post-001",
                canonical_url="https://example.invalid/synthetic-tiktok-post-001",
                title="Synthetic TikTok Post 1",
                text_excerpt="Synthetic viewer asks how to check lunch box lid for leaks.",
                language="vi",
                metrics=[
                    ProviderMetric(
                        metric_name="VIEW_COUNT",
                        value=1200,
                        precision=Precision.EXACT,
                        source_reference="synthetic-fixture-only",
                    ),
                    ProviderMetric(
                        metric_name="LIKE_COUNT",
                        value=150,
                        precision=Precision.EXACT,
                        source_reference="synthetic-fixture-only",
                    ),
                ],
                synthetic=True,
                quality_status="VALID",
            ),
            ProviderPost(
                external_id="synthetic-tiktok-post-002",
                canonical_url="https://example.invalid/synthetic-tiktok-post-002",
                title="Synthetic TikTok Post 2",
                text_excerpt="Review hop com giu nhiet van phong chong tran.",
                language="vi",
                metrics=[
                    ProviderMetric(
                        metric_name="VIEW_COUNT",
                        value=4500,
                        precision=Precision.EXACT,
                        source_reference="synthetic-fixture-only",
                    )
                ],
                synthetic=True,
                quality_status="VALID",
            ),
        ]
        return Page(items=items[:query.limit], total_count=len(items), status=ProviderStatus.OK)

    def get_content(
        self, external_ref: str, auth: AuthContext, budget: Budget
    ) -> ProviderPost | ProviderError:
        budget_err = self._check_budget(budget)
        if budget_err:
            return budget_err

        fault_err = self._handle_simulated_fault()
        if fault_err:
            return fault_err

        if external_ref in ["not-found", "empty", "nonexistent"]:
            return ProviderError(
                error_code=ProviderStatus.EMPTY,
                provider_id=self.provider_id,
                request_id=str(uuid.uuid4()),
                retryable=False,
                message_safe=f"Content {external_ref} not found in fixture store",
            )

        return ProviderPost(
            external_id=external_ref,
            canonical_url=f"https://example.invalid/{external_ref}",
            title=f"Synthetic Post {external_ref}",
            text_excerpt="Content excerpt from synthetic fixture.",
            synthetic=True,
            quality_status="VALID",
        )

    def get_comments(
        self, external_ref: str, cursor: Optional[str], auth: AuthContext, budget: Budget
    ) -> Page[ProviderComment] | ProviderError:
        budget_err = self._check_budget(budget)
        if budget_err:
            return budget_err

        fault_err = self._handle_simulated_fault()
        if fault_err:
            return fault_err

        if external_ref in ["empty", "nonexistent"]:
            return Page(items=[], total_count=0, status=ProviderStatus.EMPTY)

        comments = [
            ProviderComment(
                comment_id="synthetic-comment-001",
                post_external_id=external_ref,
                text="Hop nay co giu am duoc canh khong ban?",
                author_id="synthetic-user-99",
                like_count=12,
                synthetic=True,
            )
        ]
        return Page(items=comments, total_count=len(comments), status=ProviderStatus.OK)

    def list_profile_posts(
        self, profile_ref: str, cursor: Optional[str], auth: AuthContext, budget: Budget
    ) -> Page[ProviderPost] | ProviderError:
        budget_err = self._check_budget(budget)
        if budget_err:
            return budget_err

        fault_err = self._handle_simulated_fault()
        if fault_err:
            return fault_err

        if profile_ref in ["empty", "nonexistent"]:
            return Page(items=[], total_count=0, status=ProviderStatus.EMPTY)

        post = ProviderPost(
            external_id=f"synthetic-profile-{profile_ref}-post-01",
            canonical_url=f"https://example.invalid/@{profile_ref}/video/1",
            title=f"Profile post by {profile_ref}",
            synthetic=True,
            quality_status="VALID",
        )
        return Page(items=[post], total_count=1, status=ProviderStatus.OK)

    def refresh_metrics(
        self, external_refs: List[str], auth: AuthContext, budget: Budget
    ) -> List[dict] | ProviderError:
        budget_err = self._check_budget(budget)
        if budget_err:
            return budget_err

        fault_err = self._handle_simulated_fault()
        if fault_err:
            return fault_err

        return [
            {
                "external_id": ref,
                "view_count": 2500,
                "like_count": 300,
                "synthetic": True,
                "observed_at": datetime.now(timezone.utc).isoformat(),
            }
            for ref in external_refs
        ]
