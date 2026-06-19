"""
Deterministic validation for export records.

Mirrors validation.py (the import side): plain code, structured Findings,
GATE/WARN severities feeding the risk score and reviewer highlighting. Reuses
the Finding/Severity/ValidationResult types so downstream code treats import
and export findings uniformly.
"""

from __future__ import annotations

from decimal import Decimal

from export_schema import ExportRecord
from validation import Finding, Severity, ValidationResult, CENT, _money_close


def check_export_totals(record: ExportRecord) -> list[Finding]:
    """Header total should reconcile against the sum of line export values."""
    out: list[Finding] = []
    if record.total_export_value == 0:
        return out  # not reported; nothing to reconcile
    line_sum = sum((li.export_value for li in record.line_items), Decimal("0"))
    tol = max(CENT, (record.total_export_value * Decimal("0.001")).quantize(CENT))
    if not _money_close(record.total_export_value, line_sum, tol):
        out.append(
            Finding(
                code="EXPORT_TOTAL",
                severity=Severity.GATE,
                message=(
                    f"header export value {record.total_export_value} != "
                    f"sum of lines {line_sum}"
                ),
                field="total_export_value",
                discrepancy=record.total_export_value - line_sum,
            )
        )
    return out


def check_export_hts(record: ExportRecord) -> list[Finding]:
    """
    For substitution matching we need a 10-digit HTS on the export line. A
    missing or malformed HTS isn't fatal (direct-identification matching can use
    other identifiers), but it's a WARN because it limits how the line can match.
    """
    out: list[Finding] = []
    for li in record.line_items:
        if li.hts_code is None:
            out.append(
                Finding(
                    code="EXPORT_HTS_MISSING",
                    severity=Severity.WARN,
                    message="no HTS on export line; substitution matching unavailable",
                    line_number=li.line_number,
                    field="hts_code",
                )
            )
        elif len(li.hts_code) != 10:
            out.append(
                Finding(
                    code="EXPORT_HTS_LENGTH",
                    severity=Severity.WARN,
                    message=f"export HTS {li.hts_code!r} is {len(li.hts_code)} digits, expected 10",
                    line_number=li.line_number,
                    field="hts_code",
                )
            )
    return out


def validate_export(record: ExportRecord) -> ValidationResult:
    result = ValidationResult()
    result.findings += check_export_totals(record)
    result.findings += check_export_hts(record)
    return result
