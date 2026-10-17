"""Pure checkout/data path rules shared by HTTP, CLI, caches and templates."""

import os
from pathlib import Path


def project_root() -> Path:
    root = Path(os.getenv("CV_CUSTOMIZER_ROOT", Path(__file__).resolve().parents[1])).expanduser()
    if not root.is_absolute():
        raise ValueError('CV_CUSTOMIZER_ROOT must be an absolute checkout path')
    return root.resolve()


def data_root() -> Path:
    root = Path(os.getenv("AUTO_CV_DATA_ROOT", project_root() / "data")).expanduser()
    return (root if root.is_absolute() else project_root() / root).resolve()
