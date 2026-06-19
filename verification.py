"""
External verification signals: grounding and consistency sampling.

These are the verification checks beyond arithmetic reconciliation. Unlike the
deterministic checks in validation.py (which run with no model and are fully
tested), these depend on the model / API, so this file is runnable-but-UNTESTED
scaffolding — the same status as api_extract.py. The pure functions that don't
need the API (the comparison/aggregation logic) are tested; the API-calling
parts are marked.

Three signals, feeding FieldSignals in risk_score.py:

  - grounding: does the value actually appear in the source region it was cited
    from? A purely local check if extraction returned bounding boxes + the page
    text; needs the rendered page text, which the extraction step can return.

  - consistency sampling: re-extract (or re-ask) and measure where fields
    disagree across runs. Needs the API. Reserve for high-risk documents.

  - second-method: compare against a deterministic parse (for structured files)
    or a cheaper model. The deterministic-parse comparison is tested; the
    cheaper-model path needs the API.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Optional


# --- grounding (local, testable) --------------------------------------------

def value_is_grounded(value: str, source_region_text: str) -> bool:
    """
    Does `value` appear in the text of the region it was cited from?

    Normalizes whitespace and currency formatting so '124,000.00' matches
    '124000' etc. This is a local check — no API — once you have the region's
    OCR/text, which the extraction step can attach via provenance bbox.
    """
    if not value or not source_region_text:
        return False
    v = _normalize_number_or_text(value)
    region = _normalize_number_or_text(source_region_text)
    return v in region


def _canon_number(tok: str) -> str:
    """Canonicalize a numeric token to a plain string (no sci notation, no
    trailing zeros, no thousands separators). Returns tok unchanged if not numeric."""
    cleaned = tok.replace("$", "").replace(",", "")
    if not re.fullmatch(r"[0-9]+(\.[0-9]+)?", cleaned):
        return tok
    try:
        d = Decimal(cleaned).normalize()
        s = format(d, "f")
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        return s
    except Exception:  # noqa: BLE001
        return tok


def _normalize_number_or_text(s: str) -> str:
    s = s.strip().lower()
    # if the whole string is one numeric value, canonicalize it directly
    if re.fullmatch(r"[\$\s]*[0-9.,]+\s*", s):
        return _canon_number(s.strip())
    # otherwise it's mixed text: canonicalize every numeric-looking token in
    # place so embedded numbers compare equal regardless of formatting
    s = re.sub(r"\s+", " ", s)
    parts = s.split(" ")
    return " ".join(_canon_number(p) for p in parts)


# --- consistency aggregation (local, testable) ------------------------------

def sample_disagreement(values: list[str]) -> Decimal:
    """
    Given the same field extracted across N runs, return the fraction of runs
    that disagree with the modal (most common) value. 0 = perfectly stable.

    This is the testable core; obtaining the N extractions needs the API
    (re_extract_samples below).
    """
    if not values:
        return Decimal("0")
    norm = [_normalize_number_or_text(v) for v in values]
    counts: dict[str, int] = {}
    for v in norm:
        counts[v] = counts.get(v, 0) + 1
    modal = max(counts.values())
    return Decimal(len(norm) - modal) / Decimal(len(norm))


# --- API-dependent parts (UNTESTED scaffolding) -----------------------------

def re_extract_samples(pdf_file_id: str, n: int = 3, temperature: float = 0.4) -> list[dict]:
    """
    UNTESTED. Re-run extraction n times to feed sample_disagreement.

    Wire this to the same call as api_extract.extract_7501_from_pdf, but with
    temperature > 0 so runs can differ, and collect the raw field dicts. Confirm
    the model id, the temperature parameter, and structured-output syntax
    against docs.claude.com.
    """
    raise NotImplementedError(
        "Wire to the live API like api_extract.py; "
        "loop n times at temperature>0 and return the field dicts. "
        "Confirm parameters against docs.claude.com."
    )


def second_model_agrees(field_value: str, cheaper_model_value: str) -> bool:
    """
    Local comparison once you have both values. Getting cheaper_model_value
    needs the API (a second extraction with a smaller/cheaper model). The
    comparison itself is testable and shown here.
    """
    return _normalize_number_or_text(field_value) == _normalize_number_or_text(
        cheaper_model_value
    )
