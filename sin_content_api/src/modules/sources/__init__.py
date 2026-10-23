"""
SIN Content Intelligence - Data Source Providers Module
"""
from .provider_protocol import (
    SourceProvider,
    ProviderCapabilities,
    ProviderCapabilityStatus,
    ProviderStatus,
    Platform,
    RecordType,
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
from .offline_fixture_adapter import OfflineFixtureAdapter
from .customer_import_adapter import CustomerImportAdapter
from .tiktok_official_adapter import TikTokOfficialAdapter
from .provider_registry import ProviderRegistry, default_registry

__all__ = [
    "SourceProvider",
    "ProviderCapabilities",
    "ProviderCapabilityStatus",
    "ProviderStatus",
    "Platform",
    "RecordType",
    "RetrievalMethod",
    "Precision",
    "ProviderMetric",
    "ProviderPost",
    "ProviderComment",
    "SearchQuery",
    "Budget",
    "AuthContext",
    "ProviderError",
    "Page",
    "OfflineFixtureAdapter",
    "CustomerImportAdapter",
    "TikTokOfficialAdapter",
    "ProviderRegistry",
    "default_registry",
]
