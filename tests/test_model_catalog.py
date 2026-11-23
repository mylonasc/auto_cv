"""TRF follow-up: live provider model catalog with typed contracts.

Default tests use injected fake transports; no network or subprocess runs.
Real-provider verification is an explicit manual check (Settings panel against
a configured backend), not part of this suite.
"""

import pytest

from src import model_catalog as catalog
from src.config import PROVIDER_DEFAULTS
from server_application.backend.services.model_catalog import ModelCatalogService


def ollama_payload(*names):
    return {"models": [{"name": name, "size": 1} for name in names]}


def google_payload(*entries):
    return {"models": [{"name": name, "supportedGenerationMethods": methods}
                        for name, methods in entries]}


def test_parse_ollama_tags_sorts_and_ignores_malformed_entries():
    assert catalog.parse_ollama_tags(ollama_payload("b-model", "a-model")) == ["a-model", "b-model"]
    assert catalog.parse_ollama_tags({"models": [{"name": "ok"}, {"size": 1}, "junk", {"name": 3}]}) == ["ok"]
    assert catalog.parse_ollama_tags({}) == []
    assert catalog.parse_ollama_tags({"models": None}) == []


def test_parse_google_models_keeps_only_generate_content_ids():
    payload = google_payload(
        ("models/gemini-3.8-flash", ["generateContent"]),
        ("models/gemini-2.5-flash-image", ["generateContent", "generateImages"]),
        ("models/embedding-001", ["embedContent"]),
        ("other/gemini-3.8-flash", ["generateContent"]),
        ("models/broken", []),
    )
    assert catalog.parse_google_models(payload) == ["models/gemini-2.5-flash-image", "models/gemini-3.8-flash"]
    assert catalog.parse_google_models({}) == []


def test_google_models_follows_bounded_pages():
    calls = []

    def fetch(url, *, timeout):
        calls.append(url)
        assert "key=secret" in url
        assert "pageSize" in url
        if "pageToken=second" in url:
            return google_payload(("models/gemini-3.8-flash", ["generateContent"]))
        assert "pageToken" not in url
        return {**google_payload(("models/gemini-3.5-flash", ["generateContent"])),
                "nextPageToken": "second"}

    assert catalog.google_models("secret", fetch=fetch) == ["models/gemini-3.5-flash", "models/gemini-3.8-flash"]
    assert len(calls) == 2


def test_ollama_models_queries_tags_endpoint():
    def fetch(url, *, timeout):
        assert url == "http://ollama:11434/api/tags"
        assert timeout == catalog.OLLAMA_TIMEOUT
        return ollama_payload("gemma4:31b")

    assert catalog.ollama_models("http://ollama:11434/", fetch=fetch) == ["gemma4:31b"]


def test_service_returns_live_catalog_with_injected_transports():
    service = ModelCatalogService(
        ollama_host="http://ollama:11434", google_api_key="secret",
        ollama_fetcher=lambda url, *, timeout: ollama_payload("gemma4:31b"),
        google_fetcher=lambda url, *, timeout: google_payload(("models/gemini-3.8-flash", ["generateContent"])))
    import asyncio
    result = asyncio.run(service.get_catalog())
    assert result == {"ollama": {"models": ["gemma4:31b"], "error": None, "live": True},
                      "google": {"models": ["models/gemini-3.8-flash"], "error": None, "live": True}}


def test_service_isolates_failures_and_uses_fallbacks_without_raising():
    def fail(url, *, timeout):
        raise ConnectionError("refused")

    service = ModelCatalogService(ollama_host="http://down:11434", google_api_key="secret",
                                  ollama_fetcher=fail, google_fetcher=fail)
    import asyncio
    result = asyncio.run(service.get_catalog())
    assert result["ollama"] == {"models": [], "error": result["ollama"]["error"], "live": False}
    assert "http://down:11434" in result["ollama"]["error"]
    assert result["google"]["models"] == catalog.GOOGLE_FALLBACK_MODELS
    assert result["google"]["live"] is False
    assert "secret" not in result["google"]["error"]


def test_service_requires_no_key_leak_and_caches_with_refresh():
    calls = []

    def fetch(url, *, timeout):
        calls.append(url)
        return ollama_payload("gemma4:31b")

    service = ModelCatalogService(ollama_host="http://ollama:11434", google_api_key=None,
                                  ollama_fetcher=fetch)
    import asyncio
    first = asyncio.run(service.get_catalog())
    second = asyncio.run(service.get_catalog())
    assert first == second and len(calls) == 1
    third = asyncio.run(service.get_catalog(refresh=True))
    assert third == first and len(calls) == 2
    assert third["google"]["error"] is not None and "GEMINI_API_KEY" in third["google"]["error"]


def test_catalog_endpoint_returns_typed_shape_and_supports_refresh(client, services):
    fetches = []

    def fake(url, *, timeout):
        fetches.append(url)
        if "generativelanguage" in url:
            return google_payload(("models/gemini-3.8-flash", ["generateContent"]))
        return ollama_payload("gemma4:31b")

    services.model_catalog = ModelCatalogService(ollama_host="http://ollama:11434", google_api_key="secret",
                                                 ollama_fetcher=fake, google_fetcher=fake)
    body = client.get("/v1/models/available").json()
    assert body == {"ollama": {"models": ["gemma4:31b"], "error": None, "live": True},
                    "google": {"models": ["models/gemini-3.8-flash"], "error": None, "live": True}}
    assert len(fetches) == 2
    again = client.get("/v1/models/available").json()
    assert again == body and len(fetches) == 2
    refreshed = client.get("/v1/models/available", params={"refresh": "true"}).json()
    assert refreshed == body and len(fetches) == 4


def test_default_google_model_is_stable_not_retired_preview():
    assert PROVIDER_DEFAULTS["google"] in catalog.GOOGLE_FALLBACK_MODELS
    assert "preview" not in PROVIDER_DEFAULTS["google"]
