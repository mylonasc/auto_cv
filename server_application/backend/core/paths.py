"""Shared path/bootstrap helpers for backend modules."""

from __future__ import annotations

import os
import sys

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CV_CUSTOMIZER_ROOT = os.getenv(
    "CV_CUSTOMIZER_ROOT",
    os.path.abspath(os.path.join(BACKEND_ROOT, "../..")),
)
DATA_ROOT = os.getenv("AUTO_CV_DATA_ROOT", os.path.join(CV_CUSTOMIZER_ROOT, "data"))

CV_DATA_DIR = os.path.join(DATA_ROOT, "cv_section_data")
ARTIFACTS_DIR = os.path.join(DATA_ROOT, "artifacts")
CACHE_DIR = os.path.join(DATA_ROOT, "cache")
JOBS_DIR = os.path.join(DATA_ROOT, "jobs")
WORKING_CVS_DIR = os.path.join(DATA_ROOT, "working_cvs")
SUBMISSIONS_DIR = os.path.join(DATA_ROOT, "submissions")


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


def ensure_data_dirs() -> None:
    """Ensure data dirs.

    Returns:
        TODO: describe return value.
    """
    os.makedirs(DATA_ROOT, exist_ok=True)
    os.makedirs(CV_DATA_DIR, exist_ok=True)
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(JOBS_DIR, exist_ok=True)
    os.makedirs(WORKING_CVS_DIR, exist_ok=True)
    os.makedirs(SUBMISSIONS_DIR, exist_ok=True)
