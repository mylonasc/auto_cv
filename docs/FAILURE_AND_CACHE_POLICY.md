# Failure and cache policy (RFK-07)

## Stage outcomes

Required posting, statement rewrite, bullet analysis and role synthesis stages
are **fail closed**. A successful analysis snapshot contains all requested
assessments; a provider/parsing/validation error does not become an unscored
bullet in an otherwise successful job. There is no supported partially-scored CV
success mode. Empty source experience remains a valid empty result.

`StageFailure` identifies the stage and role/bullet identity (or posting field).
Its public message contains exception type, not raw provider messages that may
contain credentials or full inputs. The runner marks initial execution failed;
standalone posting/rescore/render HTTP operations return 502. A failed rerender
does not change an existing successful job's analysis or publish new artifacts.
Rescoring accumulates and validates all requested responses before applying a
single working-copy update; failure does not persist a partly-rescored draft.
Parallel operations cancel and await sibling tasks on failure/cancellation.

The one permitted degraded result is field-level posting extraction when a
successful model call returns an empty/placeholder skills or qualifications
field. Those fields have explicit `provenance` entries with `status: fallback`,
`method: posting_heuristic_v1` and a reason; normal fields have `status: success`
and `method: model`. The UI labels heuristic fields. Token/section heuristics use
the actual posting; when no evidence is found the value is `Not identified in
posting`, not invented skills or qualifications. A failed model call is not
silently converted to heuristic success. Historical records without provenance
are left unchanged and do not acquire inferred provenance.

## Rendering

XeLaTeX runs in temporary scratch space with noninteractive halt-on-error,
checked exit status and a 120-second timeout. Process errors, absent executable,
timeout, absent PDF and empty PDF are failures. Only a successful nonempty output
is moved to the requested path. The shared artifact writer checks output again
and refuses existing target names, so a stale PDF cannot masquerade as new output.
Requested outputs are published as one result, not as successful partial output
when a later requested output fails. Unreferenced scratch/output files may remain
after thread cancellation or multi-file publication failure; no broad cleanup is
performed. See [PERSISTENCE_LIFECYCLE.md](PERSISTENCE_LIFECYCLE.md) for cancellation
and conservative retention rules. Offline tests mock only the process boundary;
they do not establish real template compilation quality.

## Cache identity and recovery

The v2 envelope is `{ "format": 2, "entries": { "<digest>": <assessment> } }`.
Keys hash:

- stage, exact effective chain inputs and raw posting;
- effective posting analysis, including fallback provenance;
- configured non-secret provider/model/options plus resolved SDK sampling/model
  defaults, endpoint and installed provider SDK version;
- actual prompt text, response/assessment JSON schemas and cache format version.

Changing content, posting analysis, model/provider/settings/endpoint, prompts or
schemas produces a miss. Selection/render policies do not affect scoring and are
not part of the scoring key. Role context and child scores affect synthesis.
Transient role/bullet IDs do not prevent reuse for identical effective input.
Callers constructing an analyzer without explicit model identity do not reuse
or write scoring entries; the shared HTTP/CLI pipeline supplies that identity.
Server-side model aliases that change behind the same endpoint/name cannot be
detected automatically; change the configured model name or isolate the cache
when changing those deployments.

Cache access is an optimization, not a requirement for valid analysis. Entries
are validated on read and write, and returned by value. Invalid assessments are
logged, treated as misses and replaced only by fresh validated analysis. Corrupt,
legacy or unsupported cache files are logged and ignored; disk writes for that
cache instance are disabled so the original remains recoverable. Valid new
analysis can still be cached in memory. Atomic write failures are logged and
retained as `cache.warnings`, but do not fail successful analysis. No credential
values are persisted in cache entries/keys. Concurrent cache operations use the
application-owned lock; multi-process sharing is unsupported.

Regression coverage: `tests/test_outcomes.py`, `tests/test_analysis_cache.py`,
`tests/test_lifecycle.py` and the typed frontend mapping tests.
