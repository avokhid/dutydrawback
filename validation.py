"""
Deterministic validation for extracted 7501 entries.

This is the "ordinary code, not AI" reliability layer. None of these checks
ask the model whether it thinks it was right; they verify the extracted data
against arithmetic and known structural constraints. This is where a large
share of numeric extraction errors get caught, precisely because the data is
over-determined — the same quantities and values are implied in multiple
places and have to reconcile.

Each check emits a `Finding` rather than a bare boolean. The structure (which
field, what failed, severity, the discrepancy) is what later feeds the
per-field risk score and tells the reviewer UI exactly which field to
highlight. A check that just returned False would throw that information away.

Severity:
  - GATE   : near-dispositive. A field that trips a gate routes to review
             regardless of other signals (e.g. line math doesn't reconcile).
  - WARN   : suspicious, contributes to the risk score but isn't decisive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from datetime import date, timedelta
from enum import Enum
from typing import Optional

from schema import Entry7501, LineItem


class Severity(str, Enum):
    GATE = "gate"
    WARN = "warn"


@dataclass
class Finding:
    code: str                      # stable machine code, e.g. "LINE_MATH"
    severity: Severity
    message: str                   # human-readable, for the reviewer
    line_number: Optional[int] = None   # which line, if line-scoped
    field: Optional[str] = None         # which field to highlight
    discrepancy: Optional[Decimal] = None  # signed size of the mismatch

    def __str__(self) -> str:
        loc = ""
        if self.line_number is not None:
            loc = f" [line {self.line_number}"
            if self.field:
                loc += f".{self.field}"
            loc += "]"
        return f"{self.severity.value.upper()} {self.code}{loc}: {self.message}"


@dataclass
class ValidationResult:
    findings: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True only if nothing tripped a gate."""
        return not any(f.severity is Severity.GATE for f in self.findings)

    @property
    def gates(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.GATE]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.WARN]


# Money comparisons need a tolerance — rounding to the cent across many lines
# legitimately drifts a little. A penny per line is normal; a dollar is not.
CENT = Decimal("0.01")


def _money_close(a: Decimal, b: Decimal, tol: Decimal) -> bool:
    return abs(a - b) <= tol


# --- Individual checks -------------------------------------------------------
# Each takes the entry and returns a list of findings (possibly empty).


def check_line_math(entry: Entry7501) -> list[Finding]:
    """
    Per line: quantity * unit_price should equal entered_value.
    This is the highest-yield numeric check — it catches a misread quantity,
    price, or value because the three are mutually constraining.
    """
    out: list[Finding] = []
    for li in entry.line_items:
        expected = (li.quantity * li.unit_price).quantize(CENT)
        # tolerance scales a little with line size; a cent is too tight on a
        # six-figure line where unit price itself was rounded.
        tol = max(CENT, (li.entered_value * Decimal("0.001")).quantize(CENT))
        if not _money_close(expected, li.entered_value, tol):
            out.append(
                Finding(
                    code="LINE_MATH",
                    severity=Severity.GATE,
                    message=(
                        f"qty {li.quantity} x unit {li.unit_price} = {expected}, "
                        f"but entered value is {li.entered_value}"
                    ),
                    line_number=li.line_number,
                    field="entered_value",
                    discrepancy=(li.entered_value - expected),
                )
            )
    return out


def check_totals_reconcile(entry: Entry7501) -> list[Finding]:
    """
    Header totals should equal the sum of the line items. When they don't, and
    exactly one line is off by the difference, we can often point at the
    culprit line — but even just knowing the total is wrong is a strong signal.
    """
    out: list[Finding] = []

    def reconcile(label: str, header: Decimal, line_sum: Decimal, code: str):
        tol = max(CENT, (header * Decimal("0.001")).quantize(CENT))
        if not _money_close(header, line_sum, tol):
            diff = header - line_sum
            f = Finding(
                code=code,
                severity=Severity.GATE,
                message=(
                    f"header {label} {header} != sum of lines {line_sum} "
                    f"(off by {diff})"
                ),
                field=label,
                discrepancy=diff,
            )
            # Triangulation: if a single line equals the discrepancy, name it.
            culprit = _find_single_line_equal_to(entry, abs(diff), code)
            if culprit is not None:
                f.line_number = culprit
                f.message += f"; line {culprit} matches the gap"
            out.append(f)

    reconcile(
        "total_entered_value",
        entry.total_entered_value,
        sum((li.entered_value for li in entry.line_items), Decimal("0")),
        "TOTAL_VALUE",
    )
    reconcile(
        "total_duty",
        entry.total_duty,
        sum((li.duty_paid for li in entry.line_items), Decimal("0")),
        "TOTAL_DUTY",
    )
    return out


def _find_single_line_equal_to(
    entry: Entry7501, amount: Decimal, code: str
) -> Optional[int]:
    field_name = "entered_value" if code == "TOTAL_VALUE" else "duty_paid"
    matches = [
        li.line_number
        for li in entry.line_items
        if _money_close(getattr(li, field_name), amount, CENT)
    ]
    return matches[0] if len(matches) == 1 else None


def check_hts_structure(entry: Entry7501) -> list[Finding]:
    """
    HTSUS codes are 10 digits. (The schema already strips punctuation and
    rejects non-digits; here we check length, which is a content rule, not a
    type rule.) Wrong length usually means a digit was dropped or merged.
    """
    out: list[Finding] = []
    for li in entry.line_items:
        if len(li.hts_code) != 10:
            out.append(
                Finding(
                    code="HTS_LENGTH",
                    severity=Severity.WARN,
                    message=f"HTS {li.hts_code!r} is {len(li.hts_code)} digits, expected 10",
                    line_number=li.line_number,
                    field="hts_code",
                )
            )
    return out


def check_mpf_bounds(entry: Entry7501) -> list[Finding]:
    """
    Merchandise Processing Fee is an ad valorem fee with a statutory floor and
    ceiling per entry. The exact dollar amounts change by regulation, so they
    live in a config the domain expert maintains — not hardcoded here. This
    check is a placeholder showing where that rule plugs in; with real bounds
    it flags an MPF that falls outside the legal range, a classic sign of a
    misread fee.
    """
    out: list[Finding] = []
    # Bounds intentionally left as None until sourced from current regs.
    mpf_floor: Optional[Decimal] = None
    mpf_ceiling: Optional[Decimal] = None
    if mpf_floor is None or mpf_ceiling is None:
        return out  # not configured; skip rather than guess
    if not (mpf_floor <= entry.total_mpf <= mpf_ceiling):
        out.append(
            Finding(
                code="MPF_BOUNDS",
                severity=Severity.WARN,
                message=f"total MPF {entry.total_mpf} outside [{mpf_floor}, {mpf_ceiling}]",
                field="total_mpf",
            )
        )
    return out


def check_drawback_window(entry: Entry7501, claim_date: date) -> list[Finding]:
    """
    Drawback under TFTEA requires the claim within 5 years of importation.
    An entry date that puts the claim outside that window isn't an extraction
    error per se, but it's an eligibility gate the claim can't pass, so we
    surface it the same way.
    """
    out: list[Finding] = []
    # 5 years, accounting for leap days roughly via 365*5 + 1 buffer day.
    deadline = entry.entry_date + timedelta(days=365 * 5 + 1)
    if claim_date > deadline:
        out.append(
            Finding(
                code="DRAWBACK_WINDOW",
                severity=Severity.GATE,
                message=(
                    f"entry {entry.entry_date} + 5yr = {deadline}, "
                    f"but claim date {claim_date} is past the window"
                ),
                field="entry_date",
            )
        )
    return out


def validate_entry(entry: Entry7501, claim_date: Optional[date] = None) -> ValidationResult:
    """Run the full deterministic check suite over one entry."""
    result = ValidationResult()
    result.findings += check_line_math(entry)
    result.findings += check_totals_reconcile(entry)
    result.findings += check_hts_structure(entry)
    result.findings += check_mpf_bounds(entry)
    if claim_date is not None:
        result.findings += check_drawback_window(entry, claim_date)
    return result
