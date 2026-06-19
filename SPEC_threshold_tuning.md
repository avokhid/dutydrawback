# Labeled test set & threshold tuning — process spec

This is a **process, not a module**. The thresholds in the code
(`MatchConfig.auto_pass_threshold`, `risk_score` `auto_pass_max_error`) ship as
*starting points, not measured values*. This spec is how you replace those
guesses with numbers measured against ground truth — turning the review
percentage from an assertion into a governed output.

## Why it exists

Every threshold in the system trades reviewer load against escaped errors. You
cannot set it sensibly by feel. You set it by measuring, on a labeled set, what
fraction auto-passes and what fraction of true errors that auto-passed pile
contains — then picking the threshold that satisfies your error policy.

## Building the labeled set

1. **Sample representatively.** A few hundred to a few thousand fields/matches,
   spanning the *real* document mix — including the messy classes (faxed scans,
   odd vendor formats, multi-page entries) in roughly their production
   proportion. Tuning on clean documents and deploying on faxes produces a
   fictional error rate.
2. **Label with a trusted reviewer** — ideally a licensed drawback specialist
   for the rule-dependent judgments. For each field: correct value + whether the
   system's extraction was right. For each match: correct designation + whether
   the system's match was right.
3. **Store it versioned**, separate from production data, so you can re-run
   tuning and track drift over time.

## Tuning procedure

1. Run the full pipeline over the labeled set; collect each field's risk score
   (`risk_score.score_field`) and each match's confidence
   (`CandidateMatch.confidence`), alongside the ground-truth correct/incorrect.
2. **Sweep the threshold** from 0 to 1. At each value compute: auto-pass rate,
   review rate, errors caught (in the review pile), errors missed (in the
   auto-pass pile). The interactive tuner shown earlier visualizes exactly this
   curve — reproduce its computation here against real labels.
3. **Pick by policy.** Fix the constraint you actually care about (e.g. "≤0.5%
   of auto-passed fields may be wrong") and read off the highest auto-pass rate
   that still satisfies it. That auto-pass rate *is* your measured review
   percentage.
4. **Check calibration.** Bin fields by predicted error probability; in each
   bin, the predicted rate should match the observed error rate. If a "5%" bin
   actually errs 15% of the time, the score is miscalibrated — correct it (e.g.
   isotonic/Platt scaling) before trusting threshold policy.

## Refinements

- **Per-field-type thresholds.** A misread duty figure costs more than a misread
  description. Set stricter thresholds where errors are expensive; the code
  already supports per-call thresholds.
- **Drift re-measurement.** New vendors/formats shift the distribution.
  Re-measure on fresh labeled samples periodically. The reviewer corrections
  captured in normal operation (`learning.Correction` records) are the raw
  material for next quarter's labeled set — the same activity that feeds the
  learning loop feeds the test set.

## Moving from heuristic to learned scoring

`risk_score.score_field` is a transparent weighted blend today. Once the labeled
set is large enough, train a calibrated model (logistic regression or
gradient-boosted trees) to predict P(field is wrong) from the signal vector, and
drop it into `score_field` — the signature is built to stay the same, so nothing
downstream changes. Keep the weighted version as a fallback and for
explainability.

## What "done" looks like

You can state, with evidence: "At our current threshold, X% of fields auto-pass
and the auto-passed error rate is Y%, measured on a representative labeled set of
N items last refreshed on DATE." That sentence — not a guess — is the deliverable.
