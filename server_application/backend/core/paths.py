"""Shared path/bootstrap helpers for backend modules."""

from __future__ import annotations

import os
import sys

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CV_CUSTOMIZER_ROOT = os.getenv(
    "CV_CUSTOMIZER_ROOT",
    os.path.abspath(os.path.join(BACKEND_ROOT, "../..")),
)


def ensure_project_root_on_path() -> None:
    if CV_CUSTOMIZER_ROOT not in sys.path:
        sys.path.append(CV_CUSTOMIZER_ROOT)


def ensure_backend_root_on_path() -> None:
    if BACKEND_ROOT not in sys.path:
        sys.path.append(BACKEND_ROOT)
