"""
SIN Content Intelligence - SourceProvider Protocol & DTOs
Complies strictly with CONTRACTS.md and schemas/source_record.schema.json.
"""
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

class ProviderCapabilityStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    REQUIRES_AUTH = "REQUIRES_AUTH"
    UNVERIFIED = "UNVERIFIED"
    DISABLED_BY_POLICY = "DISABLED_BY_POLICY"

class ProviderStatus(str, Enum):
    OK = "OK"
    EMPTY = "EMPTY"
    PARTIAL = "PARTIAL"
    RATE_LIMITED = "RATE_LIMITED"
    AUTH_FAILED = "AUTH_FAILED"
    FORBIDDEN = "FORBIDDEN"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID_DATA = "INVALID_DATA"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    CANCELED = "CANCELED"
    RIGHTS_NOT_GRANTED = "RIGHTS_NOT_GRANTED"
    NO_APPROVED_SOURCE = "NO_APPROVED_SOURCE"

class Platform(str, Enum):
    TIKTOK = "TIKTOK"
    WEB = "WEB"
    CUSTOMER_DATA = "CUSTOMER_DATA"
    OTHER = "OTHER"

class RecordType(str, Enum):
    POST = "POST"
    COMMENT = "COMMENT"
    PROFILE = "PROFILE"
    DOCUMENT = "DOCUMENT"
    SEARCH_SIGNAL = "SEARCH_SIGNAL"

class RetrievalMethod(str, Enum):
    API = "API"
    LICENSED_PROVIDER = "LICENSED_PROVIDER"
    APPROVED_CRAWLER = "APPROVED_CRAWLER"
    CUSTOMER_IMPORT = "CUSTOMER_IMPORT"
    FIXTURE = "FIXTURE"

class Precision(str, Enum):
    EXACT = "EXACT"
    ROUNDED = "ROUNDED"
    ESTIMATED = "ESTIMATED"

class ProviderMetric(BaseModel):
    metric_name: str # VIEW_COUNT, LIKE_COUNT, COMMENT_COUNT, SHARE_COUNT, FOLLOWER_COUNT
    value: int = Field(ge=0)
    observed_at: str = Field(default_factory=utc_now_iso)
    precision: Precision = Precision.EXACT
    source_reference: str = "direct_observation"

class ProviderPost(BaseModel):
    external_id: str
    canonical_url: Optional[str] = None
    title: Optional[str] = None
    text_excerpt: Optional[str] = None
    published_at: Optional[str] = None
    observed_at: str = Field(default_factory=utc_now_iso)
    language: Optional[str] = "vi"
    organic_status: str = "UNKNOWN"
    metrics: List[ProviderMetric] = Field(default_factory=list)
    synthetic: bool = False
    quality_status: str = "VALID" # VALID, PARTIAL, QUARANTINED
    raw_payload: Optional[dict] = None

class ProviderComment(BaseModel):
    comment_id: str
    post_external_id: str
    text: str
    author_id: Optional[str] = None
    published_at: Optional[str] = None
    observed_at: str = Field(default_factory=utc_now_iso)
    like_count: Optional[int] = None
    synthetic: bool = False

class SearchQuery(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=20, ge=1, le=100)
    lookback_days: int = Field(default=30, ge=1, le=365)
    language: Optional[str] = "vi"
    cursor: Optional[str] = None

class Budget(BaseModel):
    max_requests: int = 100
    max_cost_usd: float = 0.0
    current_requests: int = 0
    current_cost_usd: float = 0.0
    timeout_seconds: float = 30.0

    def can_spend(self, cost_usd: float = 0.0) -> bool:
        if self.current_requests >= self.max_requests:
            return False
        if (self.current_cost_usd + cost_usd) > self.max_cost_usd and self.max_cost_usd > 0.0:
            return False
        return True

    def record_spend(self, cost_usd: float = 0.0) -> None:
        self.current_requests += 1
        self.current_cost_usd += cost_usd

class AuthContext(BaseModel):
    workspace_id: str
    user_id: str
    role: Optional[str] = None
    oauth_token: Optional[str] = None
    approved_source_ids: List[str] = Field(default_factory=list)

class ProviderError(BaseModel):
    error_code: str
    provider_id: str
    request_id: str
    retryable: bool
    message_safe: str
    retry_after_seconds: Optional[int] = None
    observed_at: str = Field(default_factory=utc_now_iso)
    partial_result_refs: List[str] = Field(default_factory=list)

T = TypeVar("T")

class Page(BaseModel, Generic[T]):
    items: List[T] = Field(default_factory=list)
    next_cursor: Optional[str] = None
    total_count: Optional[int] = None
    status: ProviderStatus = ProviderStatus.OK
    partial_quarantined_count: int = 0

class ProviderCapabilities(BaseModel):
    provider_id: str
    platform: Platform
    search_content: ProviderCapabilityStatus
    get_content: ProviderCapabilityStatus
    get_comments: ProviderCapabilityStatus
    list_profile_posts: ProviderCapabilityStatus
    refresh_metrics: ProviderCapabilityStatus
    live_status: str # UNVERIFIED, AUTHORIZED_IMPORT, LIVE_NOT_TESTED, READY, DISABLED_BY_POLICY
    cost_per_request_usd: float = 0.0
    requires_oauth: bool = False
    rate_limit_rpm: int = 60

class SourceProvider(ABC):
    """
    Abstract Protocol for Data Source Providers.
    No provider is allowed to bypass access controls or invent synthetic data as real.
    """
    provider_id: str
    platform: Platform

    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Returns the capability manifest of the provider."""
        pass

    @abstractmethod
    def search_content(
        self, query: SearchQuery, auth: AuthContext, budget: Budget
    ) -> Page[ProviderPost] | ProviderError:
        """Searches content matching the query."""
        pass

    @abstractmethod
    def get_content(
        self, external_ref: str, auth: AuthContext, budget: Budget
    ) -> ProviderPost | ProviderError:
        """Retrieves a single piece of content by its external reference."""
        pass

    @abstractmethod
    def get_comments(
        self, external_ref: str, cursor: Optional[str], auth: AuthContext, budget: Budget
    ) -> Page[ProviderComment] | ProviderError:
        """Retrieves comments for a content item."""
        pass

    @abstractmethod
    def list_profile_posts(
        self, profile_ref: str, cursor: Optional[str], auth: AuthContext, budget: Budget
    ) -> Page[ProviderPost] | ProviderError:
        """Lists posts by a creator profile."""
        pass

    @abstractmethod
    def refresh_metrics(
        self, external_refs: List[str], auth: AuthContext, budget: Budget
    ) -> List[dict] | ProviderError:
        """Refreshes metrics snapshots for content items."""
        pass
