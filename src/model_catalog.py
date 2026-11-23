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

# Last-resort IDs when the live query fails; the response is then explicitly
# marked not-live so the UI can warn. Kept to stable (non-preview) models.
# No metadata: token limits and sizes are only reported from live provider data.
GOOGLE_FALLBACK_MODELS = [
    {"id": "models/gemini-3.8-flash", "display": "Gemini 3.8 Flash",
     "context_window": None, "max_output_tokens": None, "size_bytes": None, "parameters": None},
    {"id": "models/gemini-3.5-flash", "display": "Gemini 3.5 Flash",
     "context_window": None, "max_output_tokens": None, "size_bytes": None, "parameters": None},
    {"id": "models/gemini-3.5-flash-lite", "display": "Gemini 3.5 Flash-Lite",
     "context_window": None, "max_output_tokens": None, "size_bytes": None, "parameters": None},
]


def parse_ollama_tags(payload: dict) -> list[dict]:
    """Extract sorted model entries with size/parameter/context metadata."""
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return []
    entries = []
    for entry in models:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            continue
        details = entry.get("details") if isinstance(entry.get("details"), dict) else {}
        size = entry.get("size")
        context = details.get("context_length")
        parameters = details.get("parameter_size")
        entries.append({
            "id": name,
            "display": None,
            "context_window": context if isinstance(context, int) and context > 0 else None,
            "max_output_tokens": None,
            "size_bytes": size if isinstance(size, int) and size > 0 else None,
            "parameters": parameters if isinstance(parameters, str) and parameters else None,
        })
    return sorted(entries, key=lambda item: item["id"])


def parse_google_models(payload: dict) -> list[dict]:
    """Keep full `models/...` IDs with display and token-limit metadata."""
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return []
    entries = []
    for entry in models:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        methods = entry.get("supportedGenerationMethods") or []
        if not isinstance(name, str) or not name.startswith("models/") or "generateContent" not in methods:
            continue
        display = entry.get("displayName")
        limit_in = entry.get("inputTokenLimit")
        limit_out = entry.get("outputTokenLimit")
        entries.append({
            "id": name,
            "display": display if isinstance(display, str) and display else None,
            "context_window": limit_in if isinstance(limit_in, int) and limit_in > 0 else None,
            "max_output_tokens": limit_out if isinstance(limit_out, int) and limit_out > 0 else None,
            "size_bytes": None,
            "parameters": None,
        })
    return sorted(entries, key=lambda item: item["id"])


def fetch_json(url: str, *, timeout: int) -> dict:
    """Default blocking transport; the service runs it off the event loop."""
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        if response.status != 200:
            raise ValueError(f"Model list request failed (HTTP {response.status})")
        return json.loads(response.read().decode("utf-8"))


def ollama_models(host: str, *, fetch=fetch_json, timeout: int = OLLAMA_TIMEOUT) -> list[dict]:
    return parse_ollama_tags(fetch(f"{host.rstrip('/')}/api/tags", timeout=timeout))


def google_models(api_key: str, *, fetch=fetch_json, timeout: int = GOOGLE_TIMEOUT) -> list[dict]:
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
    seen = {}
    for entry in models:
        seen.setdefault(entry["id"], entry)
    return sorted(seen.values(), key=lambda item: item["id"])
