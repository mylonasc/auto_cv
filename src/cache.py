"""Validated, best-effort scoring cache with explicit recoverable-file policy."""

from copy import deepcopy
import hashlib
import json
import logging
from pathlib import Path
import threading

from .analysis import Assessment
from .paths import data_root
from .storage import atomic_write_json

logger = logging.getLogger(__name__)
CACHE_FORMAT = 2


class AnalysisResultCache:
    """Unrecognized/corrupt files remain untouched; warnings expose optimization failures."""
    def __init__(self, cache_path=None):
        self._lock = threading.RLock()
        self.cache_path = str(cache_path or data_root() / 'cache' / 'analysis_results_cache.json')
        self._cache, self.warnings, self._disk_writable = {}, [], True
        self._load()

    def warn(self, message):
        self.warnings.append(message)
        logger.warning('Analysis cache: %s', message)

    def _load(self):
        with self._lock:
            path = Path(self.cache_path)
            if not path.exists():
                return
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                if not isinstance(data, dict) or data.get('format') != CACHE_FORMAT or not isinstance(data.get('entries'), dict):
                    raise ValueError('Unrecognized cache format')
                self._cache = data['entries']
            except (OSError, ValueError):
                self._cache = {}
                self._disk_writable = False
                self.warn('Unreadable/legacy cache ignored; original retained, disk writes disabled for this instance')

    def _save(self):
        with self._lock:
            if not self._disk_writable:
                return
            try:
                atomic_write_json(self.cache_path, {'format': CACHE_FORMAT, 'entries': self._cache})
            except (OSError, ValueError):
                self.warn('Persistence failed; valid analysis retained in memory only')

    def get(self, key):
        with self._lock:
            value = self._cache.get(key)
            if value is None:
                return None
            try:
                return Assessment.model_validate(value).model_dump()
            except ValueError:
                self._cache.pop(key, None)
                self.warn('Invalid cached assessment ignored; fresh analysis required')
                return None

    def set(self, key, value, persist=True):
        with self._lock:
            self._cache[key] = Assessment.model_validate(deepcopy(value)).model_dump()
            if persist:
                self._save()

    def flush(self): self._save()


def make_cache_key(scope, payload):
    """Hash effective stage inputs and identity; no content or credentials in disk keys."""
    value = json.dumps({'scope': scope, 'format': CACHE_FORMAT, 'payload': payload}, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(value.encode('utf-8')).hexdigest()
