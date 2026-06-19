# Reviewer UI — build spec for Cursor

This is a **spec, not code**, because the reviewer UI is a frontend application
(React/Next or similar) — Cursor's natural territory. The three screens were
designed in detail already; this turns those designs into build requirements and
defines how the UI talks to the Python backend.

The backend produces everything the UI needs: `CandidateMatch` objects (with
confidence, tier, signals, notes), validation `Finding`s (severity, line, field,
discrepancy), and `FieldRisk` decisions. The UI is a view-and-decide layer over
those; it does not re-implement any rule.

## Principle (carried from the design discussion)

The reviewer never investigates — they confirm or correct. Every decision is on
one screen, pre-filled with the system's proposed answer, with the uncertain
field flagged and its source proof inline. Seconds-per-decision is the product
metric. Drive the auto-pass fraction up and the per-queued-item time down.

## Three screens

### 1. Bulk-approve list (high-confidence queue)
- Source: `CandidateMatch` where `tier == AUTO_PASS`.
- Dense table: checkbox, import line, matched export, confidence. All
  pre-selected.
- Reviewer deselects anything off; one action approves the rest (Enter key).
- Deselected rows route to the detailed queue (set their tier to REVIEW).
- Endpoint: `POST /api/matches/approve` with a list of match ids.

### 2. Single-match review card (one uncertain match)
- Source: `CandidateMatch` where `tier == REVIEW`, one at a time.
- Side-by-side import vs export, fields aligned per row. Quiet fields stay
  quiet; the **signal with the lowest score** (from `match.signals`) is the one
  to highlight in amber — that's the uncertain dimension.
- Inline source proof: render the cited region from `provenance[field].bbox` on
  the page image, with the value highlighted. Do NOT make the reviewer open the
  PDF.
- Keyboard: A approve, E correct, R reject.
- "Apply to all N like this": calls the learning endpoint (see below) and clears
  the matching group.
- Endpoints: `POST /api/matches/{id}/approve|reject`, and the correction form
  for E.

### 3. Structured correction form (opens on E)
- All inputs are **structured** (dropdowns/enums), never free text for the
  decision itself — this is what makes the correction machine-readable for both
  audit and learning.
- Fields: field-being-corrected (enum), system-proposed (read-only),
  corrected-value, reason-code (`CorrectionReason` enum), optional note,
  scope (vendor/part), and "save as reusable rule" toggle with live impact count.
- On save: `POST /api/corrections` with a body matching the `Correction`
  dataclass. The backend calls `RuleStore.learn_from(...)`, which may create a
  `UomRule`/`AliasRule`; the response returns how many queued matches the new
  rule auto-resolves so the UI can show "9 matches auto-resolved".

## Backend contract (already built, Python side)

| UI needs | Backend source |
|---|---|
| match list, tiers, confidence, signals | `matching.CandidateMatch` |
| which field to highlight | lowest-scoring key in `CandidateMatch.signals`; or `Finding.field` for validation gates |
| source proof location | `provenance[field].bbox` on the schema objects |
| correction submission | `learning.Correction` -> `RuleStore.learn_from` |
| risk tier per field | `risk_score.assess_field` -> `FieldRisk` |

Recommended: a thin FastAPI layer exposing these as JSON endpoints. The
dataclasses already mirror the JSON shapes; `dataclasses.asdict` / Pydantic
`model_dump` get you most of the way.

## What NOT to do
- Don't re-implement matching, scoring, or rules in the frontend. The UI shows
  decisions and captures corrections; the Python engine owns the logic.
- Don't store decisions only in component state — every approve/correct/reject
  is an audit event and must persist via the backend.
- Don't let "save as reusable rule" default to broad scope. Default the scope to
  the most specific (vendor + part) to avoid a rule silently auto-passing wrong
  matches.
