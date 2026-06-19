# Duty drawback engine — backend core

A duty-drawback calculation system: ingest import and export documents, verify
the extracted data, match imports to exports, and compute the refund — with
uncertain cases routed to a human reviewer.

This package is the **backend core**: the deterministic engine plus the
API-integration scaffolding plus specs for the two frontend/process pieces. It
is meant to be handed to Cursor to assemble into a running application.

## Status at a glance

| Module | What it does | Status |
|---|---|---|
| `schema.py` | Import-side (7501) typed schema | tested |
| `validation.py` | Deterministic checks on imports (line math, totals, HTS, 5-yr window) | tested |
| `export_schema.py` | Export-side typed schema | tested |
| `export_validation.py` | Deterministic checks on exports | tested |
| `inventory.py` | FIFO/LIFO/low-to-high, no-double-claim guard | tested |
| `matching.py` | Entity resolution, confidence tiers, produces designations | tested |
| `calculation.py` | 99% rule, lesser-of cap, unused-merchandise | tested |
| `drawback_types.py` | Manufacturing (BOM) + rejected-merchandise types | tested |
| `risk_score.py` | Combines signals into per-field auto-pass/review tier | tested |
| `learning.py` | Reviewer corrections -> reusable rules (the flywheel) | tested |
| `api.py` | FastAPI layer: matches, approve/reject, corrections endpoints | tested |
| `verification.py` | Grounding + sampling signals (local parts) | partly tested |
| `extraction.py` | The 7501 extraction prompt (prompt-as-artifact) | n/a (text) |
| `api_extract.py` | Live API: PDF -> Entry7501 -> validation | UNTESTED |
| `SPEC_reviewer_ui.md` | Reviewer UI build spec (frontend = Cursor's job) | spec |
| `SPEC_threshold_tuning.md` | Labeled-set + threshold tuning (a process) | spec |

**42 tests pass.** The UNTESTED file (and the API parts of verification.py) need
a live API key + real documents; they are correct-looking starting points,
clearly marked, not proven code.

## Run it

```bash
pip install pydantic pytest anthropic fastapi "uvicorn[standard]" httpx --break-system-packages
python3 -m pytest -q              # 42 passing
python3 demo.py                   # import extract->validate flow
python3 demo_pipeline.py          # full pipeline: docs -> match -> refund
uvicorn api:app --reload          # the API the reviewer UI talks to (see /docs)
```

The reviewer UI lives in `reviewer_ui/` — open `reviewer_ui/reviewer.html` to see
it run, or build on `reviewer_ui/App.jsx`. Point its fetch calls at the `uvicorn`
server per the wiring table in `reviewer_ui/README.md`.

## The data flow (how the modules connect)

```
PDF/scan ─(api_extract)─► Entry7501 ─(validation)─► findings
                                │
export doc ─► ExportRecord ─(export_validation)─► findings
                                │
                  imports + exports
                                ▼
                  inventory (orders lots, prevents double-claim)
                                ▼
                  matching (scores, tiers: auto-pass / review / reject)
                                ▼
        designations ──► calculation (99%, lesser-of) ──► refund
                                │
    review-tier matches ─► reviewer UI ─► corrections ─► learning
                                                            │
                                  rules feed back into matching
```

The seams are deliberate: `calculation.py` consumes `Designation` objects;
`matching.py` produces them. `matching.py` consumes a `UomTable`; `learning.py`
writes to it. Each module depends only on `schema.py` and the layer directly
below it, so they stay independently testable.

## Important: things deliberately NOT faked

These are hooks, not guesses — faking them would produce wrong or non-compliant
output:

- **MPF floor/ceiling** (`validation.py`): left None; the check skips rather than
  hardcoding regulatory dollar amounts that drift. Source from current regs.
- **Model id + structured-output syntax** (`api_extract.py`, `verification.py`):
  take from docs.claude.com when wiring the live API; they change.
- **Thresholds** (`matching.py`, `risk_score.py`): starting points, not measured.
  Replace via the process in `SPEC_threshold_tuning.md`.
- **Substitution lesser-of basis**: `calculation.py` refuses to compute
  substitution drawback without the exported-article duty basis rather than
  guessing a non-compliant figure.
- **Drawback rule edge cases**: mechanics are faithful to the statute as scoped,
  but manufacturing yield/apportionment and similar edge cases need a licensed
  drawback specialist to confirm. Treat outputs as defensible estimates pending
  domain validation, not filing-ready figures.

## Suggested assembly order for Cursor

1. Package the modules (`src/drawback/`, `__init__.py`, relative imports). Keep
   all 42 tests green — they are the contract; a refactor that changes expected
   *values* (not just imports) changed real behavior and needs a second look.
2. Wrap the engine in a thin FastAPI layer exposing the endpoints in
   `SPEC_reviewer_ui.md`.
3. Test `api_extract.py` against real 7501 PDFs with a key — the riskiest
   assumption (is extraction reliable enough?). Wire grounding/sampling once
   extraction returns provenance.
4. Build the reviewer UI per `SPEC_reviewer_ui.md`.
5. Stand up the labeled-set tuning process per `SPEC_threshold_tuning.md` to
   replace placeholder thresholds with measured ones.

## Still out of scope (named, deferred earlier)

- **ACE filing integration** — set aside from the start; it's what separates an
  estimator from a filing tool. Needs ABI/CBP certification.
- **Document long-tail hardening** — rotated scans, odd vendor formats, Excel
  with merged cells (parse structured files deterministically, not via the model).
- **Cost/latency at scale** — batch processing, prompt caching.
