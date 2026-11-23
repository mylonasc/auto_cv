"""TRF follow-up: live provider model catalog with injected transports.

Queries Ollama (`/api/tags`) and the Gemini Developer API (`models.list`) for
models the configured credentials can actually use, so the settings dropdown
never offers a retired ID. No network or subprocess runs at import time; the
service layer injects runners (fakes in tests, thread-offloaded ``urllib`` in
production) and the HTTP boundary shares one TTL cache per provider.
"""

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OLLAMA_TIMEOUT = 10
GOOGLE_TIMEOUT = 15
GOOGLE_PAGE_SIZE = 100
GOOGLE_MAX_PAGES = 3

# Last-resort names when the live query fails; the response is then explicitly
# marked not-live so the UI can warn. Kept to stable (non-preview) models.
GOOGLE_FALLBACK_MODELS = [
    "models/gemini-3.8-flash",
    "models/gemini-3.5-flash",
    "models/gemini-3.5-flash-lite",
]


def parse_ollama_tags(payload: dict) -> list[str]:
    """Extract sorted Ollama model names; unknown shapes yield no models."""
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return []
    names = {entry.get("name") for entry in models if isinstance(entry, dict)}
    return sorted(name for name in names if isinstance(name, str) and name)


def parse_google_models(payload: dict) -> list[str]:
    """Keep full `models/...` IDs that support generateContent, sorted."""
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return []
    names = []
    for entry in models:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        methods = entry.get("supportedGenerationMethods") or []
        if isinstance(name, str) and name.startswith("models/") and "generateContent" in methods:
            names.append(name)
    return sorted(names)


def fetch_json(url: str, *, timeout: int) -> dict:
    """Default blocking transport; the service runs it off the event loop."""
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        if response.status != 200:
            raise ValueError(f"Model list request failed (HTTP {response.status})")
        return json.loads(response.read().decode("utf-8"))


def ollama_models(host: str, *, fetch=fetch_json, timeout: int = OLLAMA_TIMEOUT) -> list[str]:
    return parse_ollama_tags(fetch(f"{host.rstrip('/')}/api/tags", timeout=timeout))


def google_models(api_key: str, *, fetch=fetch_json, timeout: int = GOOGLE_TIMEOUT) -> list[str]:
    """All generateContent models across bounded pages; key never logged."""
    models: list[str] = []
    token: str | None = None
    for _ in range(GOOGLE_MAX_PAGES):
        query = {"pageSize": GOOGLE_PAGE_SIZE, "key": api_key}
        if token:
            query["pageToken"] = token
        payload = fetch(f"https://generativelanguage.googleapis.com/v1beta/models?{urlencode(query)}",
                        timeout=timeout)
        if not isinstance(payload, dict):
            break
        models.extend(parse_google_models(payload))
        token = payload.get("nextPageToken")
        if not isinstance(token, str) or not token:
            break
    return sorted(set(models))
