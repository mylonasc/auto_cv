# Canonical CV schema (RFK-02)

The single supported CV uses `src.domain.CVData` for storage, API input/output,
processing, and CLI input. Frontend types live in `src/types/cv.ts` under the
active frontend. `candidate` contains metadata only; content has one location:

```json
{
  "schema_version": 1,
  "candidate": {"candidate_id": "charilaos_mylonas", "full_name": "", "profile": {}},
  "content_format": "latex",
  "document": null,
  "personal_statement": "",
  "alternative_statements": [],
  "experience_sections": [
    {"company": "Example", "duration": "2020-2024", "position": "Engineer", "text_items": ["Experience"]}
  ],
  "cv_template": {"template_id": "template2", "template_path": null, "revision": null, "experience_section_title": "Work Experience"},
  "motivation_letter_template": {"template_id": "default_motivation_letter", "template_path": null}
}
```

Unknown fields and invalid types are rejected instead of silently discarded.
The additive `content_format` field defaults to `latex` for existing documents;
`plain_text` opts into render-time escaping without changing stored text. Working
copies and render snapshots retain it. No existing files are rewritten on read.
Template layouts, resources, precedence and remaining hard-coded content are
documented in [TEMPLATES.md](TEMPLATES.md).
TRF-01 adds optional `document` composition and a paired, pinned managed-template
`revision`; missing/null values retain legacy behavior. Statement/experience
bindings reference top-level content, never duplicate it. Managed revisions cannot
also specify a legacy path. Contracts/import/recovery and the interim fail-closed
rendering limitation are in [TEMPLATE_STUDIO.md](TEMPLATE_STUDIO.md).
Candidate identity must match the requested CV. Template paths may be null (use
the registry ID), relative to the project, or explicit paths as supported before.
Resolution produces a rendering copy; it never changes stored paths. CLI path
overrides win over CLI ID overrides, which win over saved template references.
Unspecified CLI template options now preserve the saved choice.

## Compatibility boundary

`src.cv_storage.normalize_cv_data` handles **unversioned stored/CLI input**:

- Flat content with flat or nested candidate metadata.
- Content nested under `candidate`.
- Both locations when duplicate values agree.
- A bare list of experience entries (other fields receive defaults).
- Missing/null legacy template objects receive default references.

Missing legacy values are filled from the other location. Equal duplicates
collapse. **Unequal values, including empty versus nonempty, are conflicts**;
there is no automatic "newer wins" rule because no trustworthy revision exists.
Unknown fields, unsupported schema versions, and mismatched identity also fail.
Adaptation is deterministic, idempotent, and does not mutate its input.

Versioned documents are validated strictly. New API writes accept only the
canonical structure; duplicated historical request bodies receive HTTP 422.
The existing master endpoint aliases remain available but return the same
canonical shape as version endpoints. Both UI editing paths edit top-level
content, so a save cannot be overridden by a stale nested copy.

## Migration and recovery

No startup sweep, GET, or processing read rewrites user data. Existing version
files are preferred over old `<candidate>_cv_data.json` filenames. The old master
locations remain read-only fallbacks and appear as `master` in version listings.

On an explicit save:

1. Validate/serialize the canonical document before writing anything.
2. If replacing an existing version file, retain its exact bytes in
   `<version>.json.backup-<SHA256-of-original-bytes>.bak`. Backups are immutable,
   deduplicated by content, and excluded from version listings. Existing `.bak`
   files are never overwritten.
3. Write a temporary file in the destination directory, flush it, and atomically
   replace the version. Backup/replacement errors abort the save. Broader
   concurrent-writer and repository lifecycle rules remain RFK-06 work.

Saving a legacy-filename master creates the canonical version file and leaves
the legacy source untouched. Reads of conflicting/malformed stored data return
HTTP 409 with the field requiring resolution. To recover, preserve the original
and any backups, compare both conflicting copies, and explicitly author a
canonical JSON document selecting the intended content. Do not delete the other
copy before retaining a recovery file. Restore a backup by copying its bytes to
the original version filename with the application stopped; it will be adapted
again on the next read. Never modify a content-addressed backup in place.

This change does not migrate the repository's existing user files automatically.
Offline tests exercise adaptation, real API/CLI processing, both configured CV
templates, and failure recovery; PDF execution is faked at the process boundary.
Real XeLaTeX compilation remains the explicit smoke check in `tests/README.md`.
