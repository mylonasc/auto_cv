"""Small atomic JSON/file primitive shared by concrete filesystem repositories."""

import json
import os
from pathlib import Path
import tempfile


def atomic_write_bytes(path: str | Path, content: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as target:
            temporary = Path(target.name)
            target.write(content)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def atomic_write_json(path: str | Path, value) -> None:
    atomic_write_bytes(path, json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2).encode("utf-8"))
