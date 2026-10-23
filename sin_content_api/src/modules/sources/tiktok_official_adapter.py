"""
Official TikTok API Adapter.
Strict compliance: Gated by official OAuth token.
Live status remains UNVERIFIED until conditional live test T034 passes with authorized account.
Strictly prohibits scraping fallbacks or captcha workarounds.
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
    ProviderMetric,
    ProviderPost,
    ProviderComment,
    SearchQuery,
    Budget,
    AuthContext,
    ProviderError,
    Page,
)

class TikTokOfficialAdapter(SourceProvider):
    provider_id = "tiktok_official"
    platform = Platform.TIKTOK

    def __init__(self, api_base_url: str = "https://open.tiktokapis.com/v2"):
        self.api_base_url = api_base_url

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id=self.provider_id,
            platform=self.platform,
            search_content=ProviderCapabilityStatus.REQUIRES_AUTH,
            get_content=ProviderCapabilityStatus.REQUIRES_AUTH,
            get_comments=ProviderCapabilityStatus.REQUIRES_AUTH,
            list_profile_posts=ProviderCapabilityStatus.REQUIRES_AUTH,
            refresh_metrics=ProviderCapabilityStatus.REQUIRES_AUTH,
            live_status="UNVERIFIED", # Unverified until authorized OAuth token is approved & validated
            cost_per_request_usd=0.005,
            requires_oauth=True,
            rate_limit_rpm=60,
        )

    def _validate_auth(self, auth: AuthContext) -> Optional[ProviderError]:
        """
        Enforce valid OAuth token. If missing or invalid, return AUTH_FAILED.
        NO unapproved scraping fallback or captcha bypass is allowed.
        """
        if not auth.oauth_token or not auth.oauth_token.startswith("act."):
            return ProviderError(
                error_code=ProviderStatus.AUTH_FAILED,
                provider_id=self.provider_id,
                request_id=str(uuid.uuid4()),
                retryable=False,
                message_safe="Official TikTok API requires authorized OAuth access token (act.*). Unapproved crawlers are banned.",
            )
        return None

    def search_content(
        self, query: SearchQuery, auth: AuthContext, budget: Budget
    ) -> Page[ProviderPost] | ProviderError:
        auth_err = self._validate_auth(auth)
        if auth_err:
            return auth_err

        if not budget.can_spend(0.005):
            return ProviderError(
                error_code=ProviderStatus.BUDGET_EXCEEDED,
                provider_id=self.provider_id,
                request_id=str(uuid.uuid4()),
                retryable=False,
                message_safe="Cost budget exceeded for live TikTok API call",
            )
        budget.record_spend(0.005)

        # In live mode with approved OAuth token, this would call upstream API
        return Page(items=[], total_count=0, status=ProviderStatus.EMPTY)

    def get_content(
        self, external_ref: str, auth: AuthContext, budget: Budget
    ) -> ProviderPost | ProviderError:
        auth_err = self._validate_auth(auth)
        if auth_err:
            return auth_err

        return ProviderError(
            error_code=ProviderStatus.UNAVAILABLE,
            provider_id=self.provider_id,
            request_id=str(uuid.uuid4()),
            retryable=True,
            message_safe="Live TikTok upstream unavailable in offline mode",
        )

    def get_comments(
        self, external_ref: str, cursor: Optional[str], auth: AuthContext, budget: Budget
    ) -> Page[ProviderComment] | ProviderError:
        auth_err = self._validate_auth(auth)
        if auth_err:
            return auth_err

        return Page(items=[], total_count=0, status=ProviderStatus.EMPTY)

    def list_profile_posts(
        self, profile_ref: str, cursor: Optional[str], auth: AuthContext, budget: Budget
    ) -> Page[ProviderPost] | ProviderError:
        auth_err = self._validate_auth(auth)
        if auth_err:
            return auth_err

        return Page(items=[], total_count=0, status=ProviderStatus.EMPTY)

    def refresh_metrics(
        self, external_refs: List[str], auth: AuthContext, budget: Budget
    ) -> List[dict] | ProviderError:
        auth_err = self._validate_auth(auth)
        if auth_err:
            return auth_err

        return []
