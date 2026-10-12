# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""
Reproducibility module for LITHOS - run manifest, caching, resume, ledger.
"""
from __future__ import annotations
from lithos._version import VERSION
import hashlib
import json
import logging
import os
import pickle
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from lithos.models import Record, RunManifest, RunLedger, SearchQuery

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A cached search result."""
    key: str
    query_hash: str
    source: str
    records: list[Record]
    timestamp: str
    expires_at: Optional[str] = None


class RunCache:
    """File-based cache for search results and intermediate data."""

    def __init__(self, cache_dir: Path, ttl_days: int = 30):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_days * 86400
        self._index_path = cache_dir / "cache_index.json"
        self._index: dict[str, dict] = self._load_index()

    def _load_index(self) -> dict:
        if self._index_path.exists():
            try:
                return json.loads(self._index_path.read_text())
            except Exception:
                return {}
        return {}

    def _save_index(self):
        self._index_path.write_text(json.dumps(self._index, indent=2))

    def _make_key(self, source: str, query: SearchQuery, limit: int) -> str:
        """Generate cache key from source, query, and limit."""
        content = f"{source}|{query.boolean_query}|{query.filters}|{limit}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def get(self, source: str, query: SearchQuery, limit: int) -> Optional[list[Record]]:
        """Retrieve cached results if valid."""
        key = self._make_key(source, query, limit)
        entry_info = self._index.get(key)
        if not entry_info:
            return None

        # Check expiry
        if entry_info.get("expires_at"):
            try:
                expiry = datetime.fromisoformat(entry_info["expires_at"])
                if datetime.now(timezone.utc) > expiry:
                    self.delete(key)
                    return None
            except Exception:
                pass

        # Load records
        cache_file = self.cache_dir / f"{key}.pkl"
        if not cache_file.exists():
            self.delete(key)
            return None

        try:
            with cache_file.open("rb") as f:
                entry = pickle.load(f)
            logger.info(f"Cache hit: {source} - {query.boolean_query[:50]}")
            return entry.records
        except Exception as e:
            logger.warning(f"Cache read failed: {e}")
            self.delete(key)
            return None

    def set(self, source: str, query: SearchQuery, limit: int, records: list[Record], ttl_days: Optional[int] = None):
        """Store results in cache."""
        key = self._make_key(source, query, limit)
        cache_file = self.cache_dir / f"{key}.pkl"

        expires_at = None
        if ttl_days is not None:
            expires_at = (datetime.now(timezone.utc).timestamp() + ttl_days * 86400)
            expires_at = datetime.fromtimestamp(expires_at).isoformat()
        elif self.ttl_seconds:
            expires_at = (datetime.now(timezone.utc).timestamp() + self.ttl_seconds)
            expires_at = datetime.fromtimestamp(expires_at).isoformat()

        entry = CacheEntry(
            key=key,
            query_hash=hashlib.sha256(query.boolean_query.encode()).hexdigest()[:16],
            source=source,
            records=records,
            timestamp=datetime.now(timezone.utc).isoformat(),
            expires_at=expires_at,
        )

        try:
            with cache_file.open("wb") as f:
                pickle.dump(entry, f)
            self._index[key] = {
                "source": source,
                "query": query.boolean_query[:100],
                "limit": limit,
                "record_count": len(records),
                "timestamp": entry.timestamp,
                "expires_at": expires_at,
            }
            self._save_index()
            logger.info(f"Cache stored: {source} - {len(records)} records")
        except Exception as e:
            logger.error(f"Cache write failed: {e}")

    def delete(self, key: str):
        """Delete a cache entry."""
        cache_file = self.cache_dir / f"{key}.pkl"
        if cache_file.exists():
            cache_file.unlink()
        if key in self._index:
            del self._index[key]
            self._save_index()

    def clear(self):
        """Clear all cache."""
        for f in self.cache_dir.glob("*.pkl"):
            f.unlink()
        self._index = {}
        self._save_index()

    def stats(self) -> dict:
        """Get cache statistics."""
        total_size = sum(f.stat().st_size for f in self.cache_dir.glob("*.pkl"))
        return {
            "entries": len(self._index),
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "cache_dir": str(self.cache_dir),
        }


def create_run_manifest(
    run_id: str,
    parameters: dict,
    queries: list[SearchQuery],
    sources_used: list[str],
) -> RunManifest:
    """Create a new run manifest."""
    return RunManifest(
        run_id=run_id,
        lithos_version=VERSION,
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        started_at=datetime.now(timezone.utc).isoformat(),
        config_hash=hashlib.sha256(json.dumps(parameters, sort_keys=True).encode()).hexdigest()[:16],
        parameters=parameters,
        queries=queries,
        sources_used=sources_used,
    )


def finalize_run_manifest(
    manifest: RunManifest,
    total_found: int,
    total_after_dedup: int,
    validation_summary: dict[str, int],
    output_hashes: dict[str, str],
):
    """Finalize run manifest with results."""
    manifest.completed_at = datetime.now(timezone.utc).isoformat()
    manifest.total_records_found = total_found
    manifest.total_records_after_dedup = total_after_dedup
    manifest.validation_summary = validation_summary
    manifest.output_hashes = output_hashes


def save_run_manifest(manifest: RunManifest, path: Path):
    """Save run manifest to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest.to_json())


def load_run_manifest(path: Path) -> RunManifest:
    """Load run manifest from file."""
    data = json.loads(path.read_text())
    # Convert queries
    queries = [SearchQuery(**q) for q in data.get("queries", [])]
    data["queries"] = queries
    return RunManifest(**data)


def compute_ledger(
    current_records: list[Record],
    previous_records: list[Record],
    run_id: str,
    previous_run_id: Optional[str] = None,
) -> RunLedger:
    """Compute ledger of changes between runs."""
    current_ids = {r.id: r.content_hash for r in current_records}
    previous_ids = {r.id: r.content_hash for r in previous_records}

    unchanged = []
    new = []
    changed = []
    removed = []

    for rid, chash in current_ids.items():
        if rid in previous_ids:
            if previous_ids[rid] == chash:
                unchanged.append(rid)
            else:
                changed.append(rid)
        else:
            new.append(rid)

    for rid in previous_ids:
        if rid not in current_ids:
            removed.append(rid)

    return RunLedger(
        run_id=run_id,
        previous_run_id=previous_run_id,
        unchanged=unchanged,
        new=new,
        changed=changed,
        removed=removed,
    )


def save_ledger(ledger: RunLedger, path: Path):
    """Save ledger to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(ledger), indent=2))


def load_ledger(path: Path) -> RunLedger:
    """Load ledger from file."""
    data = json.loads(path.read_text())
    return RunLedger(**data)


def compute_file_hash(path: Path) -> str:
    """Compute SHA256 hash of a file."""
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_records_hash(records: list[Record]) -> str:
    """Compute hash of all records for change detection."""
    hasher = hashlib.sha256()
    for r in sorted(records, key=lambda x: x.id):
        hasher.update(r.content_hash.encode())
    return hasher.hexdigest()[:16]


class ReproducibilityManager:
    """Manages reproducibility artifacts for a run."""

    def __init__(self, run_dir: Path, run_id: str):
        self.run_dir = run_dir
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id
        self.manifest: Optional[RunManifest] = None
        self.cache = RunCache(run_dir / "cache")
        self.ledger: Optional[RunLedger] = None

    def start_run(self, parameters: dict, queries: list[SearchQuery], sources: list[str]):
        """Initialize a new run."""
        self.manifest = create_run_manifest(self.run_id, parameters, queries, sources)
        # Try to load previous run for ledger
        prev_manifests = sorted(self.run_dir.glob("manifest_*.json"))
        if prev_manifests:
            prev = load_run_manifest(prev_manifests[-1])
            self.ledger = RunLedger(run_id=self.run_id, previous_run_id=prev.run_id)

    def get_cached(self, source: str, query: SearchQuery, limit: int) -> Optional[list[Record]]:
        """Get cached results."""
        return self.cache.get(source, query, limit)

    def set_cached(self, source: str, query: SearchQuery, limit: int, records: list[Record]):
        """Cache results."""
        self.cache.set(source, query, limit, records)

    def finalize(self, records: list[Record], validation_summary: dict, output_files: list[Path]):
        """Finalize run and save all artifacts."""
        if not self.manifest:
            raise RuntimeError("Run not started")

        # Compute output hashes
        output_hashes = {}
        for f in output_files:
            if f.exists():
                output_hashes[f.name] = compute_file_hash(f)

        # Finalize manifest
        finalize_run_manifest(
            self.manifest,
            total_found=len(records),  # This should be before dedup
            total_after_dedup=len([r for r in records if r.dedup_master]),
            validation_summary=validation_summary,
            output_hashes=output_hashes,
        )

        # Save manifest
        manifest_path = self.run_dir / f"manifest_{self.run_id}.json"
        save_run_manifest(self.manifest, manifest_path)

        # Save ledger if we have previous records
        if self.ledger and hasattr(self, '_previous_records'):
            self.ledger = compute_ledger(records, self._previous_records, self.run_id, self.ledger.previous_run_id)
            ledger_path = self.run_dir / f"ledger_{self.run_id}.json"
            save_ledger(self.ledger, ledger_path)

        # Save cache stats
        cache_stats = self.cache.stats()
        (self.run_dir / f"cache_stats_{self.run_id}.json").write_text(json.dumps(cache_stats, indent=2))

        return self.manifest, self.ledger

    def load_previous_records(self, records: list[Record]):
        """Load previous records for ledger computation."""
        self._previous_records = records