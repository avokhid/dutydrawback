# Reviewer UI

A working prototype of the reviewer console described in `SPEC_reviewer_ui.md`.
Built so Cursor has real frontend code to integrate, not just a spec to re-derive.

## Two files

- **`reviewer.html`** — standalone, runnable. Open it in a browser (double-click,
  or `python3 -m http.server` then visit it). No build step; it transpiles in the
  browser via Babel-standalone and loads React from a CDN. This is for *seeing it
  work*, not production.
- **`App.jsx`** — the actual React component, for integrating into a real app
  (Vite/Next/CRA). This is the file Cursor should build on.

## What it does

Four connected views over shared state, matching the spec:

1. **Overview** — the triage dashboard. Two big counts (ready-to-approve vs
   needs-review) are the entry points; completion % and approved/rejected tallies
   below. Clicking a count enters that flow.
2. **Bulk approve** — dense high-confidence list, all pre-selected. Deselect what
   looks off (it dims and routes to review), approve the rest with one button or
   the Enter key.
3. **Single review** — one uncertain match. Import and export aligned per row;
   every field quiet except the one flagged in amber (the uncertain dimension).
   The engine's suggestion and the inline source proof sit below. Keyboard: `A`
   approve, `E` correct, `R` reject, `P` toggle proof.
4. **Correction form** — opens on `E`. All-structured inputs (so the correction is
   machine-readable for audit and learning), with the "save as reusable rule"
   toggle showing how many queued matches it would auto-resolve.

The triage logic actually runs on the sample data: approving/correcting updates
the counts, rules "auto-resolve" a batch, the completion % moves.

## Design intent

This is an instrument, not a marketing page. Dark, dense, calm. Color is reserved
for meaning: green = confident/approved, amber = look here / uncertain, clay =
problem/rejected, blue = structure and learned-rule actions. The reviewer's eye is
engineered toward the single flagged field; everything the system is sure about
stays visually quiet. Speed is the point — the whole thing is keyboard-drivable.

## Wiring to the backend (replace the sample data)

The component is structured so the seams are obvious. Replace:

| In `App.jsx` | With |
|---|---|
| `HIGH_CONF` seed | `GET /api/matches?tier=auto_pass` → `CandidateMatch[]` |
| `REVIEW_QUEUE` seed | `GET /api/matches?tier=review` (include `signals`, `provenance`) |
| `approveBulk`, `approveOne`, `rejectOne` | `POST /api/matches/:id/approve|reject` |
| `saveCorrection` | `POST /api/corrections` (body = `Correction` shape); response returns `impact` count |
| `item.uncertain` | lowest-scoring key in `CandidateMatch.signals` |
| `item.proof` | `provenance[field].bbox` → render the page-image crop with the value highlighted |

The one piece this prototype fakes that needs real work: **inline proof is text
here**, but the spec calls for rendering the actual page-image region from the
bounding box. That's the page-image rendering Cursor needs to add — it's what lets
the reviewer confirm against the source without opening the PDF.

## Quality floor

Responsive, keyboard-navigable, visible focus rings, `prefers-reduced-motion`
respected. Built to integrate, not to demo-and-discard.
