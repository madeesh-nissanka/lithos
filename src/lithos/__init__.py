# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""
LITHOS: Literature Retrieval and Source Validation for Scoping Reviews

Expert-grade tool for systematic and scoping review literature retrieval,
validation, screening, and reporting.
"""

from lithos.models import (
    Record,
    SearchQuery,
    SearchResult,
    ValidationResult,
    ScreenState,
    ScreenDecision,
    RecordStatus,
)
from lithos.adapters import (
    BaseAdapter,
    AdapterRegistry,
    init_adapters,
    get_adapter,
    get_enabled_adapters,
    registry,
)
from lithos.query import QueryBuilder, SearchProfile
from lithos.dedupe import deduplicate, DedupCluster
from lithos.validate import validate_record, check_retraction
from lithos.screen import ScreeningRules, ScreeningSession
from lithos.export import export_records, ExportFormat
from lithos.report import generate_prisma_flow, generate_search_report
from lithos.analytics import compute_analytics, AnalyticsResult
from lithos.reproducibility import RunManifest, RunLedger
from lithos.presets import get_preset, list_presets, get_all_profiles, ALL_PRESETS


def __getattr__(name: str):
    """Lazily expose the CLI ``main`` entry point (avoids import side effects)."""
    if name == "main":
        from lithos.cli import main as _main

        return _main
    raise AttributeError(f"module 'lithos' has no attribute {name!r}")


from lithos._version import VERSION

__version__ = VERSION
__author__ = "Madeesh P. Nissanka"
__license__ = "MIT"
__all__ = [
    "Record",
    "SearchQuery",
    "SearchResult",
    "ValidationResult",
    "ScreenState",
    "ScreenDecision",
    "RecordStatus",
    "BaseAdapter",
    "AdapterRegistry",
    "init_adapters",
    "get_adapter",
    "get_enabled_adapters",
    "registry",
    "QueryBuilder",
    "SearchProfile",
    "deduplicate",
    "DedupCluster",
    "validate_record",
    "check_retraction",
    "ScreeningRules",
    "ScreeningSession",
    "ScreenDecision",
    "export_records",
    "ExportFormat",
    "generate_prisma_flow",
    "generate_search_report",
    "compute_analytics",
    "AnalyticsResult",
    "RunManifest",
    "RunLedger",
    "main",
    "get_preset",
    "list_presets",
    "get_all_profiles",
    "ALL_PRESETS",
]