# Tests

Runs the service in Docker and drives it over HTTP with static payloads, so what is tested is
the deployed artifact — same image, same `/generate` — rather than the fill functions in
isolation. The generated PDF and a render of each page land in `tests/output/` for review.

```bash
docker compose -f tests/docker-compose.yml up --build --abort-on-container-exit --exit-code-from tests
```

Exit code is non-zero if any check fails. Against an already-running service:

```bash
DOCGEN_BASE_URL=http://localhost:8000 python tests/verify_noc.py
```

## Why this has to run in Docker

The image carries LibreOffice, so the NOC is really converted to PDF here. On a developer
machine without it, `/generate` falls back to returning the `.docx` and **nothing about the
rendered result is observable** — not the Arabic shaping, not the page order, not the
right-to-left layout. Every bidi bug listed below was invisible until this ran in the container.

## verify_noc.py

**Emirates ID format.** The NOC printed the maid's EID exactly as the ERP stores it, which is
free text, so it went out unpunctuated instead of as 784-YYYY-NNNNNNN-C. Formatting happens in
`variable_enrichment`. A value that is not 15 digits cannot be repaired by formatting, so it
prints as given and the service says so — this asserts it is neither reformatted nor invented.

**Bidi on the Arabic page.** A left-to-right value inside right-to-left text gets reordered
unless it is fenced in Unicode isolates. Three separate places needed it, and each produced a
different visible defect:

| Where | Symptom before |
|---|---|
| Substituted values (`doc_utils`) | `26 August, 2026` printed as `August, 2026 26` |
| Static template text (`scripts/build_noc_schengen_docx.py`) | `+971 505544143` printed as `505544143 971+` |
| Values inside a composed Arabic clause (`variable_enrichment`) | the EID printed as `8-1234567-1988-784` |

Separately, the EID's hyphens were line-break opportunities, so it split across a line and the
halves landed in right-to-left order (`784-1988-` / `8-1234567`). It now uses non-breaking
hyphens; the checks normalise those back to `-` before asserting.

**Reading Arabic back out of a PDF is lossy**, in two ways that matter when writing assertions
here. A lam-alef ligature comes back as its two letters in visual order, so `لا` extracts as
`ال`; and words on this page are emitted right-to-left, so a multi-word phrase never appears
contiguously even when the page is perfect. The probes are therefore single words chosen to
avoid lam-alef. The page renders in `tests/output/` are the real check on layout.
