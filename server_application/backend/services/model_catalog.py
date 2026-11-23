"""TRF follow-up: provider model catalog with TTL cache and safe errors.

One service instance per application; entries expire after ``CACHE_TTL_S``.
Every provider resolves independently: a failure yields an explanatory error
string on that provider only, never an exception, so the settings panel can
always render. Google credentials come from server-side configuration only;
clients never send keys through this API.
"""

import asyncio
import os
import time

from src.model_catalog import (
    GOOGLE_FALLBACK_MODELS,
    fetch_json,
    google_models,
    ollama_models,
)

CACHE_TTL_S = 300


class ModelCatalogService:
    def __init__(self, *, ollama_host=None, google_api_key=None,
                 ollama_fetcher=None, google_fetcher=None):
        self.ollama_host = ollama_host or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        # Explicit None (vs unset) disables Google rather than reading env.
        self.google_api_key = google_api_key if google_api_key is not None else os.getenv("GEMINI_API_KEY")
        self.ollama_fetcher = ollama_fetcher or fetch_json
        self.google_fetcher = google_fetcher or fetch_json
        self._cache: dict[str, tuple[float, dict]] = {}

    def _cached(self, provider: str):
        entry = self._cache.get(provider)
        if entry is not None and time.monotonic() - entry[0] < CACHE_TTL_S:
            return entry[1]
        return None

    def _ollama(self):
        try:
            models = ollama_models(self.ollama_host, fetch=self.ollama_fetcher)
        except Exception as error:
            return {"models": [], "error": f"Ollama is not reachable at {self.ollama_host} ({error}).",
                    "live": False}
        if not models:
            return {"models": [], "error": f"Ollama at {self.ollama_host} reported no models.", "live": False}
        return {"models": models, "error": None, "live": True}

    def _google(self):
        if not self.google_api_key:
            return {"models": [], "error": "GEMINI_API_KEY is not configured on the backend.", "live": False}
        try:
            models = google_models(self.google_api_key, fetch=self.google_fetcher)
        except Exception as error:
            return {"models": [dict(entry) for entry in GOOGLE_FALLBACK_MODELS],
                    "error": f"Google model list failed ({error}); showing stable fallback IDs.", "live": False}
        if not models:
            return {"models": [dict(entry) for entry in GOOGLE_FALLBACK_MODELS],
                    "error": "Google reported no generateContent models; showing stable fallback IDs.", "live": False}
        return {"models": models, "error": None, "live": True}

    async def get_catalog(self, *, refresh=False):
        providers = ("ollama", "google")
        if not refresh:
            cached = {provider: self._cached(provider) for provider in providers}
            if all(cached.values()):
                return cached
        fresh = await asyncio.gather(
            asyncio.to_thread(self._ollama),
            asyncio.to_thread(self._google),
        )
        now = time.monotonic()
        result = {}
        for provider, entry in zip(providers, fresh):
            self._cache[provider] = (now, entry)
            result[provider] = entry
        return result
