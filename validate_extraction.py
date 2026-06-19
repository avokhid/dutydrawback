"""
Live-extraction validation harness.

THE HONEST BOUNDARY: this script performs the validation that's been the
system's #1 unknown — does extraction hold up on real, messy 7501s? It CANNOT
run in the build environment (no API key, no real PDFs). It runs in YOUR
environment: point it at a folder of real 7501 PDFs, set ANTHROPIC_API_KEY, and
it produces a scorecard. The code is written and structured; what it needs is
real inputs, which is exactly the assumption being tested.

What it measures, per document and in aggregate:
  - extraction outcome: succeeded / failed-schema / errored
  - validation findings: how many GATE (blocking) vs WARN (advisory) per doc
  - null rate: how often the model returned null ("I wasn't sure") — the honest
    uncertainty signal; a high null rate means extraction is shaky on that doc
  - latency and (if surfaced) token usage per call — the cost/latency picture
  - a clear PASS / NEEDS-REVIEW / FAIL verdict per document

Why this shape: the goal isn't "did it produce a number" but "can we trust the
number." A doc that extracted but tripped a line-math gate is NOT a pass — it's
caught, which is the system working, but it tells you extraction misread
something. The scorecard surfaces that distinction.

Usage:
    export ANTHROPIC_API_KEY=...
    python3 validate_extraction.py /path/to/folder_of_7501_pdfs
    python3 validate_extraction.py /path/to/one.pdf --json results.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class DocResult:
    filename: str
    outcome: str                      # "extracted" | "schema_error" | "error"
    verdict: str = "unknown"          # "pass" | "needs_review" | "fail"
    gate_findings: int = 0
    warn_findings: int = 0
    null_fields: int = 0
    total_fields: int = 0
    latency_s: Optional[float] = None
    error: Optional[str] = None
    findings: list[str] = field(default_factory=list)

    @property
    def null_rate(self) -> float:
        return (self.null_fields / self.total_fields) if self.total_fields else 0.0


def _count_nulls(obj, nulls=0, total=0):
    """Walk an extracted dict counting null leaf fields vs total leaf fields —
    the model's own uncertainty signal about transcribed *data*.

    The ``provenance`` subtree is skipped on purpose: its bbox/confidence fields
    are extraction scaffolding that is routinely null (a model reading a PDF
    rarely returns pixel bounding boxes), and counting them swamps the signal —
    a perfectly clean extraction would otherwise read as ~40% null. We want "how
    often was the model unsure about a value," not "how often was a bbox absent."
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "provenance":
                continue
            nulls, total = _count_nulls(v, nulls, total)
    elif isinstance(obj, list):
        for v in obj:
            nulls, total = _count_nulls(v, nulls, total)
    else:
        total += 1
        if obj is None:
            nulls += 1
    return nulls, total


def validate_one(pdf_path: str) -> DocResult:
    """Run one real PDF through extraction + validation. Needs API key + network."""
    from api_extract import extract_7501_from_pdf
    from validation import validate_entry
    from validation import Severity

    name = os.path.basename(pdf_path)
    t0 = time.time()
    try:
        entry = extract_7501_from_pdf(pdf_path)
    except Exception as exc:  # noqa: BLE001
        # Pydantic validation error => the model returned a malformed shape.
        cls = type(exc).__name__
        outcome = "schema_error" if "Validation" in cls else "error"
        return DocResult(filename=name, outcome=outcome, verdict="fail",
                         error=f"{cls}: {exc}", latency_s=round(time.time() - t0, 2))

    latency = round(time.time() - t0, 2)
    result = validate_entry(entry)
    gates = result.gates
    warns = result.warnings
    nulls, total = _count_nulls(entry.model_dump(mode="json"))

    # verdict: a gate means extraction misread something (caught, but not a pass);
    # warns or a high null rate mean needs-review; clean means pass.
    if gates:
        verdict = "needs_review"   # caught by validation — inspect what it misread
    elif warns or (total and nulls / total > 0.1):
        verdict = "needs_review"
    else:
        verdict = "pass"

    return DocResult(
        filename=name, outcome="extracted", verdict=verdict,
        gate_findings=len(gates), warn_findings=len(warns),
        null_fields=nulls, total_fields=total, latency_s=latency,
        findings=[str(f) for f in result.findings],
    )


def run_folder(path: str) -> list[DocResult]:
    if os.path.isfile(path):
        pdfs = [path]
    else:
        pdfs = [os.path.join(path, f) for f in sorted(os.listdir(path))
                if f.lower().endswith(".pdf")]
    if not pdfs:
        print(f"No PDFs found at {path}", file=sys.stderr)
        return []
    results = []
    for p in pdfs:
        print(f"  extracting {os.path.basename(p)} …", file=sys.stderr)
        results.append(validate_one(p))
    return results


def scorecard(results: list[DocResult]) -> dict:
    n = len(results)
    by_verdict = {"pass": 0, "needs_review": 0, "fail": 0, "unknown": 0}
    for r in results:
        by_verdict[r.verdict] = by_verdict.get(r.verdict, 0) + 1
    extracted = [r for r in results if r.outcome == "extracted"]
    avg_null = (sum(r.null_rate for r in extracted) / len(extracted)) if extracted else 0.0
    avg_latency = (sum(r.latency_s or 0 for r in extracted) / len(extracted)) if extracted else 0.0
    return {
        "documents": n,
        "verdicts": by_verdict,
        "extraction_success_rate": round(len(extracted) / n, 3) if n else 0,
        "avg_null_rate": round(avg_null, 3),
        "avg_latency_s": round(avg_latency, 2),
        # the headline question, answered honestly:
        "interpretation": (
            "PASS share is the fraction that extracted cleanly AND passed every "
            "deterministic check. NEEDS-REVIEW caught real issues (good — the "
            "safety net worked — but means extraction misread or was unsure). "
            "FAIL means the model couldn't produce valid structured data at all. "
            "A high avg_null_rate signals the model is frequently unsure, which on "
            "real documents is the early warning that extraction needs hardening."
        ),
    }


def main():
    ap = argparse.ArgumentParser(description="Validate 7501 extraction on real PDFs.")
    ap.add_argument("path", help="a 7501 PDF or a folder of them")
    ap.add_argument("--json", help="write full results to this JSON file")
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY first. This harness needs the live API.",
              file=sys.stderr)
        raise SystemExit(2)

    results = run_folder(args.path)
    if not results:
        raise SystemExit(1)

    card = scorecard(results)
    print("\n=== Extraction validation scorecard ===")
    print(f"documents:              {card['documents']}")
    print(f"extraction success:     {card['extraction_success_rate'] * 100:.0f}%")
    print(f"verdicts:               {card['verdicts']}")
    print(f"avg null rate:          {card['avg_null_rate'] * 100:.0f}%")
    print(f"avg latency:            {card['avg_latency_s']}s")
    print("\nper document:")
    for r in results:
        line = f"  {r.verdict.upper():13} {r.filename}"
        if r.outcome == "extracted":
            line += f"  (gates {r.gate_findings}, warns {r.warn_findings}, nulls {r.null_rate*100:.0f}%)"
        else:
            line += f"  [{r.outcome}: {r.error}]"
        print(line)
    print(f"\n{card['interpretation']}")

    if args.json:
        with open(args.json, "w") as f:
            json.dump({"scorecard": card, "documents": [asdict(r) for r in results]},
                      f, indent=2)
        print(f"\nfull results -> {args.json}")


if __name__ == "__main__":
    main()
