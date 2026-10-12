# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""
Base adapter class and registry for multi-source retrieval.
"""
from __future__ import annotations
from lithos._version import VERSION
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from lithos.http import HTTPClient, RateLimiter, RetryPolicy, PolitePool
from lithos.models import Record, SearchQuery, SearchResult

logger = logging.getLogger(__name__)


@dataclass
class AdapterConfig:
    """Configuration for an adapter."""
    enabled: bool = True
    rate_limit: float = 1.0  # requests per second
    burst: int = 5
    max_retries: int = 3
    timeout: int = 30
    polite_email: Optional[str] = None
    api_key: Optional[str] = None
    extra_params: dict = field(default_factory=dict)


class BaseAdapter(ABC):
    """Base class for all source adapters."""

    name: str = "base"
    display_name: str = "Base Adapter"
    requires_api_key: bool = False
    supports_boolean: bool = True
    supports_year_filter: bool = True
    supports_type_filter: bool = False

    def __init__(self, config: Optional[AdapterConfig] = None, http_client: Optional[HTTPClient] = None):
        self.config = config or AdapterConfig()
        self.http = http_client or self._create_http_client()
        self._enabled = self.config.enabled

    def _create_http_client(self) -> HTTPClient:
        rate_limiter = RateLimiter(requests_per_second=self.config.rate_limit, burst=self.config.burst)
        retry_policy = RetryPolicy(max_attempts=self.config.max_retries)
        polite_pool = PolitePool(self.config.polite_email)
        return HTTPClient(rate_limiter, retry_policy, polite_pool, self.name, VERSION, self.config.timeout)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

    @abstractmethod
    def search(self, query: SearchQuery, limit: int = 100) -> SearchResult:
        """Execute a search query and return results."""
        pass

    @abstractmethod
    def translate_query(self, query: SearchQuery) -> str:
        """Translate a structured query to source-specific query string."""
        pass

    @abstractmethod
    def fetch_by_id(self, identifier: str, id_type: str = "doi") -> Optional[Record]:
        """Fetch a single record by identifier (DOI, PMID, arXiv ID, etc.)."""
        pass

    def _create_record(self, raw_data: dict, source: str, query_hits: list[str]) -> Record:
        """Create a Record from raw source data. Override in subclasses."""
        raise NotImplementedError

    def normalize_doi(self, doi: Optional[str]) -> Optional[str]:
        """Normalize DOI to standard format."""
        if not doi:
            return None
        doi = doi.strip().lower()
        prefixes = ["https://doi.org/", "http://doi.org/", "doi:"]
        for prefix in prefixes:
            if doi.startswith(prefix):
                doi = doi[len(prefix):]
                break
        return doi if doi else None


class AdapterRegistry:
    """Registry for managing source adapters."""

    def __init__(self):
        self._adapters: dict[str, BaseAdapter] = {}
        self._configs: dict[str, AdapterConfig] = {}

    def register(self, adapter: BaseAdapter, config: Optional[AdapterConfig] = None) -> None:
        """Register an adapter."""
        self._adapters[adapter.name] = adapter
        if config:
            self._configs[adapter.name] = config

    def get(self, name: str) -> Optional[BaseAdapter]:
        """Get an adapter by name."""
        return self._adapters.get(name)

    def get_all(self) -> list[BaseAdapter]:
        """Get all registered adapters."""
        return list(self._adapters.values())

    def get_enabled(self) -> list[BaseAdapter]:
        """Get all enabled adapters."""
        return [a for a in self._adapters.values() if a.enabled]

    def enable(self, name: str) -> bool:
        """Enable an adapter."""
        if name in self._adapters:
            self._adapters[name].enabled = True
            return True
        return False

    def disable(self, name: str) -> bool:
        """Disable an adapter."""
        if name in self._adapters:
            self._adapters[name].enabled = False
            return True
        return False

    def set_config(self, name: str, config: AdapterConfig) -> bool:
        """Update adapter configuration."""
        if name in self._adapters:
            self._adapters[name].config = config
            self._adapters[name].http = self._adapters[name]._create_http_client()
            self._configs[name] = config
            return True
        return False

    def get_config(self, name: str) -> Optional[AdapterConfig]:
        """Get adapter configuration."""
        return self._configs.get(name)

    def list_names(self) -> list[str]:
        """List all adapter names."""
        return list(self._adapters.keys())

    def list_enabled_names(self) -> list[str]:
        """List enabled adapter names."""
        return [a.name for a in self._adapters.values() if a.enabled]


# Global registry instance
registry = AdapterRegistry()

_INITIALIZED = False


def init_adapters(config: Optional[dict] = None) -> None:
    """Instantiate every adapter and register it with the global registry.

    Imports the concrete adapter modules lazily (inside this function) so that
    ``lithos.adapters`` can be imported by those modules without a cycle. Safe
    to call more than once; the registry is reset on each call.
    """
    global _INITIALIZED
    config = config or {}

    from lithos.adapters_arxiv import ArxivAdapter
    from lithos.adapters_core import COREAdapter
    from lithos.adapters_crossref import CrossrefAdapter
    from lithos.adapters_doaj import DOAJAdapter
    from lithos.adapters_europe_pmc import EuropePMCAdapter
    from lithos.adapters_openalex import OpenAlexAdapter
    from lithos.adapters_semantic_scholar import SemanticScholarAdapter
    from lithos.adapters_unpaywall import UnpaywallAdapter

    polite_email = config.get("polite_email") or config.get("scholar_mailto")

    def _cfg(key: str, **defaults: Any) -> AdapterConfig:
        section = config.get(key, {}) or {}
        merged = dict(defaults)
        merged.update({k: v for k, v in section.items() if k in AdapterConfig.__dataclass_fields__})
        if polite_email and "polite_email" in AdapterConfig.__dataclass_fields__:
            merged.setdefault("polite_email", polite_email)
        return AdapterConfig(**merged)

    registry._adapters.clear()
    registry._configs.clear()

    specs = {
        "openalex": (OpenAlexAdapter, {"rate_limit": 10.0, "burst": 10}),
        "crossref": (CrossrefAdapter, {"rate_limit": 50.0, "burst": 50}),
        "semantic_scholar": (SemanticScholarAdapter, {"rate_limit": 1.0, "burst": 5}),
        "arxiv": (ArxivAdapter, {"rate_limit": 3.0, "burst": 5}),
        "europe_pmc": (EuropePMCAdapter, {"rate_limit": 10.0, "burst": 10}),
        "core": (COREAdapter, {"enabled": False, "rate_limit": 10.0, "burst": 10}),
        "doaj": (DOAJAdapter, {"rate_limit": 5.0, "burst": 10}),
        "unpaywall": (UnpaywallAdapter, {"rate_limit": 10.0, "burst": 20}),
    }
    for name, (cls, defaults) in specs.items():
        cfg = _cfg(name, **defaults)
        registry.register(cls(cfg), cfg)

    _INITIALIZED = True


def get_adapter(name: str) -> Optional[BaseAdapter]:
    """Return a registered adapter by name (None if unknown)."""
    return registry.get(name)


def get_enabled_adapters() -> list[BaseAdapter]:
    """Return every enabled adapter in registration order."""
    return registry.get_enabled()