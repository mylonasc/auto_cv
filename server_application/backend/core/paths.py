"""Shared path/bootstrap helpers for backend modules."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoragePaths:
    """Pure path configuration. Reading or creating stores is explicit startup work."""
    root: Path

    @classmethod
    def from_env(cls):
        project = Path(os.getenv("CV_CUSTOMIZER_ROOT", Path(__file__).resolve().parents[3])).expanduser().resolve()
        root = Path(os.getenv("AUTO_CV_DATA_ROOT", project / "data")).expanduser()
        return cls((root if root.is_absolute() else project / root).resolve())

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

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CV_CUSTOMIZER_ROOT = os.getenv(
    "CV_CUSTOMIZER_ROOT",
    os.path.abspath(os.path.join(BACKEND_ROOT, "../..")),
)


def ensure_project_root_on_path() -> None:
    """Ensure project root on path.

    Returns:
        TODO: describe return value.
    """
    if CV_CUSTOMIZER_ROOT not in sys.path:
        sys.path.append(CV_CUSTOMIZER_ROOT)


def ensure_backend_root_on_path() -> None:
    """Ensure backend root on path.

    Returns:
        TODO: describe return value.
    """
    if BACKEND_ROOT not in sys.path:
        sys.path.append(BACKEND_ROOT)
