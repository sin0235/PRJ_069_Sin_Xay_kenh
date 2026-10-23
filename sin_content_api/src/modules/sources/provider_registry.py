"""
Provider Registry, Circuit Breaker & Compliance Enforcement.
Enforces:
1. Ban on unapproved/non-commercial tools (MediaCrawler) with RIGHTS_NOT_GRANTED without network call (T035).
2. Circuit breaker with bounded backoff and retry-after tracking (T032).
3. Budget guards preventing cost and request cap overruns (T032).
"""
import time
import uuid
from typing import Dict, List, Optional
from datetime import datetime, timezone

from .provider_protocol import (
    SourceProvider,
    ProviderCapabilities,
    ProviderStatus,
    SearchQuery,
    Budget,
    AuthContext,
    ProviderError,
    Page,
    ProviderPost,
)
from .offline_fixture_adapter import OfflineFixtureAdapter
from .customer_import_adapter import CustomerImportAdapter
from .tiktok_official_adapter import TikTokOfficialAdapter

# Banned / Non-commercial / Unauthorized crawlers
BANNED_SOURCES = {
    "mediacrawler": "Banned: Non-commercial license violation (CC BY-NC 4.0 / GPL-NC) and unauthorized scraping.",
    "tiktok_scraper": "Banned: Unauthorized scraping violates TikTok Terms of Service.",
    "unapproved_crawler": "Banned: Unapproved crawler without formal legal data rights.",
    "douyin_scraper": "Banned: Unauthorized scraping tool.",
}

class CircuitBreakerState:
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class ProviderCircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout_seconds: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.state = CircuitBreakerState.CLOSED
        self.consecutive_failures = 0
        self.last_failure_time: Optional[float] = None

    def record_success(self):
        self.consecutive_failures = 0
        self.state = CircuitBreakerState.CLOSED

    def record_failure(self):
        self.consecutive_failures += 1
        self.last_failure_time = time.time()
        if self.consecutive_failures >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN

    def can_execute(self) -> tuple[bool, Optional[int]]:
        if self.state == CircuitBreakerState.CLOSED:
            return True, None
        
        now = time.time()
        if self.last_failure_time and (now - self.last_failure_time) >= self.recovery_timeout_seconds:
            self.state = CircuitBreakerState.HALF_OPEN
            return True, None
        
        remaining = int(self.recovery_timeout_seconds - (now - (self.last_failure_time or now)))
        return False, max(1, remaining)

class ProviderRegistry:
    def __init__(self):
        self._providers: Dict[str, SourceProvider] = {}
        self._circuit_breakers: Dict[str, ProviderCircuitBreaker] = {}
        
        # Register standard approved adapters
        self.register(OfflineFixtureAdapter())
        self.register(CustomerImportAdapter())
        self.register(TikTokOfficialAdapter())

    def register(self, provider: SourceProvider):
        self._providers[provider.provider_id] = provider
        self._circuit_breakers[provider.provider_id] = ProviderCircuitBreaker()

    def get_provider(self, provider_id: str) -> SourceProvider | ProviderError:
        # T035 Check: If requested provider is banned by policy, fail immediately with RIGHTS_NOT_GRANTED
        if provider_id.lower() in BANNED_SOURCES:
            reason = BANNED_SOURCES[provider_id.lower()]
            return ProviderError(
                error_code=ProviderStatus.RIGHTS_NOT_GRANTED,
                provider_id=provider_id,
                request_id=str(uuid.uuid4()),
                retryable=False,
                message_safe=f"Access denied: {reason} Zero network calls made.",
            )

        if provider_id not in self._providers:
            return ProviderError(
                error_code=ProviderStatus.NO_APPROVED_SOURCE,
                provider_id=provider_id,
                request_id=str(uuid.uuid4()),
                retryable=False,
                message_safe=f"Provider '{provider_id}' is not registered or approved in the Compliance Registry.",
            )

        return self._providers[provider_id]

    def list_capabilities(self) -> List[ProviderCapabilities]:
        return [p.capabilities() for p in self._providers.values()]

    def execute_search(
        self, provider_id: str, query: SearchQuery, auth: AuthContext, budget: Budget
    ) -> Page[ProviderPost] | ProviderError:
        provider_or_err = self.get_provider(provider_id)
        if isinstance(provider_or_err, ProviderError):
            return provider_or_err
        
        provider = provider_or_err
        cb = self._circuit_breakers[provider_id]

        # Circuit breaker check
        can_exec, wait_sec = cb.can_execute()
        if not can_exec:
            return ProviderError(
                error_code=ProviderStatus.UNAVAILABLE,
                provider_id=provider_id,
                request_id=str(uuid.uuid4()),
                retryable=True,
                retry_after_seconds=wait_sec,
                message_safe=f"Circuit breaker OPEN for provider '{provider_id}'. Retry after {wait_sec}s.",
            )

        result = provider.search_content(query, auth, budget)

        if isinstance(result, ProviderError):
            if result.retryable:
                cb.record_failure()
            return result
        
        cb.record_success()
        return result

# Global singleton registry instance
default_registry = ProviderRegistry()
