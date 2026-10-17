# Application workflow and effective configuration (RFK-05)

`src/pipeline.py` is the shared application workflow:

1. Analyze posting text with the resolved analysis model.
2. Build a source document from canonical CV content and resolved template refs.
3. If alternatives exist, rewrite the statement with the configured editor,
   including the source statement among supplied alternatives.
4. Analyze complete experience with bounded concurrency, then select without
   deleting the source snapshot.

`CVProcessor` maps that run to typed HTTP results; `tools/autocv.py` maps it to
the existing CLI artifacts. `src/artifacts.py` is the common PDF/LaTeX writer for
initial outputs, rerenders, CLI outputs and CLI cover letters. The HTTP adapter
offloads blocking rendering to a thread. Artifact IDs/paths are unique per render,
not based on a timestamp that can collide within a second.

`tools/autocv-otel.py` accepts the same CLI flags and instruments the ordinary
entry point. Optional instrumentation/exporters initialize only during explicit
execution and flush/shut down in `finally`; no pipeline is copied there.

## Defaults and model roles

Application defaults live in `src/config.py`; UI initialization is generated from
that model. ModelFactory convenience defaults also reference its provider map.
The old `config/llm_defaults.yaml` is retained as historical configuration but is
not an active runtime source. API/CLI no longer silently select different models
through analyzer constructors.

Unspecified CLI analysis/editor options use the same local defaults as HTTP
(`ollama`, `gemma4:31b`), with selection min/max/threshold `1/5/4`. This deliberately
replaces the previous CLI-only cloud/threshold defaults; pass explicit flags for
the cloud presets documented in the README. Explicit template choices still win.

HTTP jobs use an explicit request config, otherwise a copy of the current server
config. Each job persists **non-secret effective settings**, and rescoring uses
that configuration rather than changed server defaults. Runtime construction can
use request credentials, but API keys/tokens/password fields are not persisted
in job/CLI effective-config metadata. Later rescoring resolves credentials through
the provider's environment/key setup; request-only credentials are not retained.
Historical jobs without effective settings use the current server config
explicitly, since their original provider settings cannot be recovered reliably.

## Stage and capability boundaries

- Posting-only analysis is an optional preview. Complete CV analysis explicitly
  includes posting analysis again and configured initial artifacts; it does not
  claim to continue an implicitly saved preview stage.
- Rendering existing analysis/working-copy edits does not rerun LLM analysis.
- The existing cover-letter workflow remains **CLI-only**. HTTP requests enabling
  it return 422 rather than silently ignoring it; the settings UI labels this
  limitation and does not offer it as an enabled HTTP feature.
- `max_section_parse_retries` is a reserved/deprecated compatibility field, not
  an effective retry loop. Structured-output/provider behavior is not represented
  as an application retry policy. RFK-07 owns explicit failure/partial semantics.
- CLI output must be a fresh directory. Existing directories are never deleted
  or replaced; choose another path. Temporary generation is cleaned up on failure.

Tests exercise configured model roles, API/CLI output/metric parity, retained
rescore settings, secret redaction, generated defaults, telemetry delegation and
cleanup, and preservation of pre-existing CLI output. Provider/LaTeX execution is
faked for deterministic validation; real instrumentation/exporter delivery and
live PDF/model behavior remain opt-in checks.
