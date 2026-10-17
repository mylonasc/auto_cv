"""Pure repository paths; module import performs no storage initialization."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from src.paths import data_root


@dataclass(frozen=True)
class StoragePaths:
    """Pure path configuration. Reading or creating stores is explicit startup work."""
    root: Path

    @classmethod
    def from_env(cls):
        return cls(data_root())

    @property
    def cvs(self): return self.root / "cv_section_data"
    @property
    def jobs(self): return self.root / "jobs"
    @property
    def working_copies(self): return self.root / "working_cvs"
    @property
    def submissions(self): return self.root / "submissions"
    @property
    def artifacts(self): return self.root / "artifacts"
    @property
    def render_records(self): return self.root / "render_records"
    @property
    def cache(self): return self.root / "cache" / "analysis_results_cache.json"
