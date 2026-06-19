# Duty drawback engine

A duty-drawback calculation system: ingest import and export documents, verify
the extracted data, match imports to exports, and compute the refund — with
uncertain cases routed to a human reviewer.

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
| `learning.py` | Reviewer corrections → reusable rules (the flywheel) | tested |
| `orchestrator.py` | Stage-by-stage pipeline runner (observability + pause/resume hooks) | tested |
| `rule_tiers.py` | Tiers each applied rule by how settled it is (statute / ruling / advisory) | tested |
| `explanation.py` | Narrates a refund line into cited, tier-tagged "how it's calculated" steps | tested |
| `rulings.py` | Ruling-tier store: relevant CBP rulings (CROSS) by HTS/provision, stale ones excluded, all marked "confirm applicability" | tested |
| `cross_connector.py` | Populates `rulings.py` from CROSS — bulk + recency sync logic (mock-tested); live source adapter is untested scaffold | tested (logic); live adapter **UNTESTED** |
| `advisory.py` | Advisory-tier transparency: adjudication patterns (not a pattern engine) + CBP discretion (out of scope by nature) | tested |
| `persistence.py` | SQLite Repository: durable claims, documents, matches, append-only audit events, pipeline state | tested |
| `verification.py` | Grounding + sampling signals (local parts) | partly tested |
| `extraction.py` | The 7501 extraction prompt (prompt-as-artifact) | n/a (text) |
| `api_extract.py` | Live API: PDF **or image (photo/scan)** → Entry7501 → validation | exercised live (PDF + JPG); no key in CI |
| `validate_extraction.py` | Live-extraction scorecard harness (the #1 unknown); scoring/verdict logic tested, live calls run in your env | tested (logic); live run needs key + PDFs |
| `degrade_pdf.py` | Test-data tool: degrades a clean PDF into realistic fax/scan/photo/lowres/rotate variants to stress-test extraction on the document long tail | dev tool (needs pypdfium2/pillow/img2pdf) |

Plus specs (`SPEC_reviewer_ui.md`, `SPEC_threshold_tuning.md`) and a full-stack layer:

| Path | Role |
|---|---|
| `backend/main.py` | FastAPI app — extraction pipeline + reviewer endpoints, serves the UI |
| `backend/reviewer_service.py` | Reviewer state on the real engine: matching, learning, `calculate_claim` refund + recovery estimate |
| `backend/mock_extract.py` | Stub extraction (no API key required) |
| `backend/static/shell_live.html` | No-build two-tab front door (Importer estimate + Reviewer console) embedding the real pages via same-origin iframes |
| `backend/static/reviewer_live.html` | No-build reviewer UI (vendored React/Babel, same-origin, live data) |
| `backend/static/estimate_live.html` | No-build recovery-estimate UI (live data from `/api/claim/estimate`) |
| `backend/static/activity_live.html` | No-build pipeline activity feed (live SSE from `/api/claim/run-stream`) |
| `backend/static/upload_live.html` | No-build document upload (front door); "Run estimate" hands off to `/drawback-type` |
| `backend/static/drawback_type_live.html` | No-build up-front drawback-type selector (drives the calculate basis) |
| `backend/static/journey_live.html` | No-build guided walkthrough (Upload → Read → Confirm → Type → Estimate → Review) |
| `backend/static/how_calculated_live.html` | No-build per-line derivation: cited, tier-tagged steps from the real engine math |
| `backend/static/bom_live.html` | No-build bill-of-materials entry for manufacturing drawback (live `/api/manufacturing/estimate`) |
| `frontend/` | Vite/TypeScript UI: upload, drawback-type, guided journey, extraction, reviewer, recovery-estimate, pipeline-run, how-it's-calculated, and bill-of-materials tabs |

**92 tests pass.** `api_extract.py`, the API parts of `verification.py`, the
live CROSS source adapter (`cross_connector.LiveCrossSource`), and the live calls
inside `validate_extraction.py` need network / credentials / real documents the
test environment can't provide — their surrounding logic is unit-tested.

> Claude's standalone `api.py` (batches 5–10) was merged into `backend/main.py` +
> `backend/reviewer_service.py` rather than run as a second server. Its
> engine-backed refund, the customer-facing recovery estimate, the live pipeline
> stream, and the up-front drawback-type selection (`/api/drawback-types` +
> `drawback_type` on the run) now feed the same-origin UIs, while our backend
> keeps the extraction pipeline and UI serving. The original `EstimateReport.jsx` /
> `estimate.html` / `ActivityFeed.jsx` / `activity.html` remain as the
> sample-data design source.
>
> The ruling and advisory tiers that `rule_tiers.py` named but left empty are now
> backed by real modules — `rulings.py` (CROSS ruling retrieval), `cross_connector.py`
> (how the store is populated/kept current), and `advisory.py` (adjudication +
> discretion transparency). They feed `/api/claim/explanation` and the
> `/how-calculated` page; they surface references and limits, never change the math.
>
> The manufacturing-BOM estimate, durable persistence, and live-extraction harness
> from Claude's `api.py` snapshot were likewise merged in rather than run as a
> second server: `POST /api/manufacturing/estimate` (+ `/bom` UI), the `/api/claims*`
> persistence endpoints (`persistence.py`), and the standalone `validate_extraction.py`
> harness (`VALIDATION_18.md`). `bom.html` / `BomEntry.jsx` remain the design source.

## Run it

### Tests + CLI demos

```bash
pip install -r requirements.txt
python -m pytest -q   # 92 passing (engine, validation, pipeline, orchestrator, explanation, rulings/CROSS, persistence, extraction-harness, API + reviewer)
python demo.py            # import extract → validate flow
python demo_pipeline.py   # full pipeline: docs → match → refund
```

### Live extraction CLI (needs API key + real PDF)

```bash
export ANTHROPIC_API_KEY=...
python api_extract.py path/to/7501.pdf
```

Confirm model id and structured-output syntax from docs.claude.com before relying on it.

### Live-extraction validation harness (the #1 unknown — needs key + real PDFs)

```bash
export ANTHROPIC_API_KEY=...
python validate_extraction.py /path/to/folder_of_7501_pdfs
python validate_extraction.py one_7501.pdf --json results.json
```

Produces a per-document PASS / NEEDS-REVIEW / FAIL scorecard plus extraction
success rate, average null rate (the model's own uncertainty signal), and latency.
See `VALIDATION_18.md` for how to read it. The scoring/verdict logic is unit-tested;
the live extraction inside is what you're validating.

> **Live run, June 2026.** The end-to-end path was exercised against the real API
> (`claude-opus-4-8`, Files API + strict tool-use) on synthetic 7501 PDFs. It works,
> and surfaced two fixes now in place: (1) the model faithfully transcribes money
> with thousands separators ("4,500.00") per the prompt, so `schema.py` now strips
> grouping commas / currency symbols deterministically before `Decimal` parsing —
> the model stays a transcriber, the parse layer normalizes; (2) the harness's null
> rate excluded the `provenance` subtree, whose bbox/confidence are routinely null,
> so a clean extraction no longer reads as ~40% "unsure." A clean doc scored PASS;
> a doc with a deliberately mismatched header total was correctly caught
> NEEDS-REVIEW by the duty-reconciliation gate. The document long-tail (faxes,
> rotated scans, odd vendor layouts) still needs real documents to validate —
> `degrade_pdf.py` manufactures realistic messy variants (fax/scan/photo/rotate)
> from a clean PDF so you can stress-test that long tail when short on real samples
> (`degrade_pdf.py clean.pdf` → feed the output folder to `validate_extraction.py`).

### Full-stack app (API + reviewer UI)

**Backend** (from project root):

```bash
uvicorn backend.main:app --reload
```

- `GET /api/health` — health check
- `POST /api/process` — upload PDF, extract, validate, return JSON
- `GET /api/claim/stats` — reviewer triage counts + engine-computed `refund`
- `GET /api/claim/estimate` — customer-facing recovery estimate (confident/potential range + per-category breakdown)
- `GET /api/claim/run-stream?drawback_type=…` — Server-Sent Events streaming each pipeline stage live (validate → match → calculate → done), with plain-language summaries; `drawback_type` is the user's up-front choice and flows into the calculate stage, which reports the basis actually used
- `GET /api/claim/source-documents` — the source files the run will process (shown up front in the activity feed)
- `GET /api/drawback-types` — the drawback bases the selector offers, each with an `estimable` flag (the engine computes the two unused bases; rejected/manufacturing are advertised but need a reason/BOM step not yet wired)
- `GET /api/claim/explanation?line=N` — step-by-step derivation of one refund line (the engine's actual arithmetic, each cited step tagged with its rule tier via `rule_tiers.py`), plus the line's relevant CBP `rulings` (ruling tier — references to confirm, never math), an `advisory` block (adjudication patterns + CBP discretion), and a `transparency` summary of what the estimate does and does not cover
- `GET /api/rulings/relevant?hts=…&provision=…` — CBP rulings (CROSS) that may bear on a line, as ruling-tier references each marked "confirm applicability"; stale (revoked/superseded) rulings excluded, samples flagged until a live CROSS ingest replaces them
- `GET /api/advisory` — the advisory transparency block: adjudication patterns (not a comprehensive engine — public data can't support one honestly) and CBP discretion (out of scope by nature)
- `GET /api/claim/import-lines` — the loaded import entry/line options the BOM picker references (manufacturing drawback ties inputs by entry+line, not HTS)
- `POST /api/manufacturing/estimate` — accepts a user-supplied bill of materials (`{article_id, quantity_exported, components:[{import_entry_number, import_line_number, quantity_per_unit, yield_factor}]}`) and returns the engine's designations + recovery; components referencing entries not in the claim are reported plainly, never guessed
- `POST /api/claims` / `GET /api/claims` — create + list durable claims (SQLite via `persistence.py`); survive restarts
- `GET /api/claims/{claim_id}/audit` — the append-only audit trail (approvals, rejections, corrections) for a claim
- `GET /api/matches?tier=auto_pass|review` — match queues for reviewer UI
- `POST /api/matches/approve` — bulk approve high-confidence matches
- `POST /api/matches/send-to-review` — demote unchecked bulk rows to review
- `POST /api/matches/{id}/approve|reject` — single-match decisions
- `POST /api/corrections` — structured correction + optional rule learning
- `POST /api/claim/reset` — reset reviewer state to the freshly-matched claim

The refund in `/api/claim/stats` is real: approved matches become `Designation`s
and run through `calculate_claim`, so the overview's dollar figure rises as you
approve and reflects the same 99%/lesser-of logic as the offline pipeline. The
`/api/claim/estimate` view runs the same engine but splits recovery into a
confident figure (auto-pass matches) and additional potential (review-tier),
presented as a range — the estimator's customer-facing deliverable.

The backend also serves nine no-build UIs (vendored React, same-origin, no npm):

- `http://localhost:8000/` — **Default landing: two-tab front door** — Importer estimate (`/journey`) + Reviewer console (`/reviewer`), each embedded as a real same-origin page (`shell_live.html`); also at `/shell`
- `http://localhost:8000/reviewer` — Match Reviewer console (`reviewer_live.html`)
- `http://localhost:8000/upload` — Document upload, the front door of a new estimate (`upload_live.html`)
- `http://localhost:8000/drawback-type` — Up-front drawback-type selector (`drawback_type_live.html`)
- `http://localhost:8000/journey` — Guided walkthrough of the whole path (`journey_live.html`)
- `http://localhost:8000/estimate` — Recovery Estimate (`estimate_live.html`)
- `http://localhost:8000/activity` — live pipeline activity feed over SSE (`activity_live.html`)
- `http://localhost:8000/how-calculated` — per-line derivation showing how the refund is computed (`how_calculated_live.html`)
- `http://localhost:8000/bom` — bill-of-materials entry for manufacturing drawback (`bom_live.html`)

`/how-calculated` answers "where does this number come from?" without a black box:
it renders `explanation.explain_line_json()` over the real engine `LineCalculation`,
so the steps are the derivation and can't drift from the figure. Each cited step is
tagged with its rule tier from `rule_tiers.py` — the math itself is statute/regulation
("firmly codified"). Below the steps it surfaces the other two tiers honestly: a
**Relevant CBP rulings** section (ruling tier, from `rulings.py` matched on the line's
HTS + provision) showing each as a reference to confirm — never as a determination and
never changing the figure — with sample rulings clearly flagged until a live CROSS
ingest replaces them; and a **What this estimate cannot tell you** panel (from
`advisory.py`) naming adjudication patterns (not a pattern engine) and CBP discretion
as explicitly out of scope.

The customer flow runs `/upload → /drawback-type → /activity`: upload stages files
(simulated extraction; real per-file extraction via `api_extract.extract_7501_from_pdf`
is the live-document test harness, the system's #1 untested assumption, left until
there's a live API key + real documents), the type selector records the drawback
basis up front and passes it as `?drawback_type=…` into the run. The engine computes
the two unused bases today; `rejected` and `manufacturing` are offered but flagged
"needs extra info" (a stated reason / a bill of materials) and fall back to the
substitution basis, which the calculate stage reports honestly rather than
mislabeling the figure. `/journey` is a self-contained, clickable tour of how the
dedicated screens join up.

`manufacturing` now has its extra-info step: `/bom` collects the bill of materials
the basis requires (which imported inputs, how many per finished unit, the yield) —
production data no uploaded document contains, so it's a structured data-entry form,
not a calculation. It posts to `/api/manufacturing/estimate`, which explodes the BOM
into per-component designations (`quantity_exported × quantity_per_unit ÷ yield`) and
runs them through the same `calculate_claim`. The engine uses exactly the numbers
entered — it does not infer or adjust the BOM, and components pointing at entries not
loaded in the claim are reported plainly rather than guessed.

`persistence.py` is the durable store (SQLite behind a `Repository` interface):
claims, documents, matches, an append-only audit trail of approvals/rejections/
corrections, and pipeline-state snapshots, all surviving restart. The `/api/claims*`
endpoints expose it; the in-memory reviewer session doesn't yet write through to it
(the next assembly step), so it stands ready rather than wired into the live flow.

`orchestrator.py` runs the engine stages as a generator of `StageEvent`s
(observability), with pause/resume hooks for halting on a GATE anomaly — the
resume path is exercised in tests but gated on durable state persistence before
production use. The activity feed drives it over the clean `demo_pipeline`
dataset for a green end-to-end run.

**Frontend** (requires Node.js + npm):

```bash
cd frontend
npm install
npm run dev
```

UI at `http://localhost:5173`, proxies `/api` to the backend.

Tabs in the app:

- **7501 Extraction** — upload PDF, validate, field highlighting
- **Match Reviewer** — overview, bulk approve, single review, correction form
- **Recovery Estimate** — customer-facing recovery range + per-category breakdown
- **Pipeline Run** — live activity feed; watch validate → match → calculate over SSE
- **How It's Calculated** — per-line derivation with cited, tier-tagged steps
- **Bill of Materials** — manufacturing-drawback BOM entry → live recovery estimate
- plus **Upload**, **Drawback Type**, and **Guided Journey** entry-flow screens

Copy `.env.example` to `.env` for `CLAIM_DATE` and `ANTHROPIC_API_KEY`.

### Extraction modes (`mock_mode`)

- **clean** — stub returns a valid entry (auto-pass)
- **corrupt** — stub returns a misread line 1 value (routed to review)
- **live** — calls Claude via `api_extract.py` (requires `ANTHROPIC_API_KEY`)

## The data flow

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

Seams are deliberate: `calculation.py` consumes `Designation` objects;
`matching.py` produces them. `matching.py` consumes a `UomTable`; `learning.py`
writes to it.

## How validation maps to the reviewer UI

Each validation `Finding` carries severity, the line, the field, and the
discrepancy:

- **GATE** findings route a field to human review regardless of other signals.
- **WARN** findings feed the per-field risk score rather than forcing review.

The `line_number` + `field` on each finding tells the reviewer UI which field
to highlight.

## What's deliberately NOT faked

- **MPF floor/ceiling** (`validation.py`): left `None`; check skips rather than hardcoding regulatory amounts.
- **Model id + structured-output syntax** (`api_extract.py`, `verification.py`): take from docs.claude.com when wiring live API.
- **Thresholds** (`matching.py`, `risk_score.py`): starting points, not measured. Replace via `SPEC_threshold_tuning.md`.
- **Substitution lesser-of basis**: `calculation.py` refuses to compute without exported-article duty basis.
- **Drawback rule edge cases**: treat outputs as defensible estimates pending domain validation, not filing-ready figures.

## Next assembly steps

1. Run `validate_extraction.py` against real 7501 PDFs — the riskiest assumption.
   The harness is built (`VALIDATION_18.md` has run instructions); it needs a live
   key + documents, which only your environment has.
2. Add page-image proof rendering from `provenance[field].bbox` (batch 4 prototype uses text proof).
3. Stand up labeled-set tuning per `SPEC_threshold_tuning.md`.
4. Wire the reviewer flow onto `persistence.py` so a session's approvals/corrections
   land in the durable audit trail (the Repository + `/api/claims*` endpoints exist;
   the in-memory reviewer state isn't yet writing through to it).

## Still out of scope

- **ACE filing integration** — needs ABI/CBP certification.
- **Document long-tail hardening** — rotated scans, odd vendor formats (use `degrade_pdf.py` to stress-test, but real samples are the true validation).
- **Cost/latency at scale** — batch processing, prompt caching.

## Batch READMEs

Earlier batches left standalone notes when filenames would clash:

- `README_3.md` — batch 3 backend core overview
- `README_4.md` — batch 4 reviewer UI prototype (`App.jsx`, `reviewer.html`); integrated into `frontend/src/reviewer/`
