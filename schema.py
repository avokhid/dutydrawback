"""
Typed schemas for drawback source documents.

This module defines the *structured target* that document extraction must
produce. The LLM's job is to fill these shapes; everything downstream
(validation, matching, calculation) operates on these objects, never on raw
document text. Keeping the schema strict is the first line of reliability:
a malformed extraction fails here, loudly, instead of silently poisoning a
duty calculation three stages later.

Scope: CBP 7501 entry summary (the import side). Other document types
(commercial invoice, bill of lading, AES/EEI export record) would get their
own schemas in sibling modules and share the same validation philosophy.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# Money is Decimal, never float. Float math leaks artifacts (0.1 + 0.2 != 0.3),
# and a duty figure that is off by a rounding artifact is a compliance problem.
Money = Decimal


def _clean_numeric(v):
    """Normalize a transcribed numeric string into Decimal-parseable form.

    The extraction prompt deliberately tells the model to transcribe figures
    verbatim ("keep digits exactly as shown; do not add or remove thousands
    separators"), so a 7501 that prints "200,000.00" or "$4,500.00" comes back
    with those characters. The model stays a faithful transcriber; this
    deterministic layer strips the presentational characters (thousands commas,
    currency symbols, whitespace) so the value parses. A bare comma-as-decimal is
    not assumed — US customs forms use period decimals — we only remove grouping.
    """
    if isinstance(v, str):
        cleaned = v.replace(",", "").replace("$", "").strip()
        return cleaned if cleaned else v
    return v


class ExtractionProvenance(BaseModel):
    """
    Where a value came from, so a reviewer (and the grounding check) can trace
    it back to the source. Every extracted field should carry one of these.
    `confidence` is the model's *self-reported* confidence: recorded, but
    treated as a weak signal — the external checks in validation.py are what
    actually decide whether a field is trustworthy.
    """

    page: int = Field(ge=1, description="1-based page number in the source PDF")
    bbox: Optional[tuple[float, float, float, float]] = Field(
        default=None, description="x0,y0,x1,y1 region the value was read from"
    )
    confidence: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="model self-reported, weak signal"
    )


class LineItem(BaseModel):
    """A single line on the 7501. The unit of the whole drawback claim."""

    line_number: int = Field(ge=1)
    hts_code: str = Field(description="10-digit HTSUS classification, digits only")
    description: str
    quantity: Decimal = Field(gt=0)
    unit_of_measure: str = Field(description="e.g. 'EA', 'CTN', 'KG', 'DOZ'")
    unit_price: Money = Field(ge=0)
    entered_value: Money = Field(ge=0, description="customs value for this line")

    # Duties, taxes, and fees actually paid on this line — the basis for the
    # 99% drawback. Stored per-line because drawback is computed per-line.
    duty_paid: Money = Field(ge=0, default=Decimal("0"))
    mpf_paid: Money = Field(ge=0, default=Decimal("0"), description="merch. processing fee")
    hmf_paid: Money = Field(ge=0, default=Decimal("0"), description="harbor maintenance fee")

    provenance: dict[str, ExtractionProvenance] = Field(
        default_factory=dict,
        description="field name -> where it was read from",
    )

    @field_validator(
        "quantity", "unit_price", "entered_value", "duty_paid", "mpf_paid", "hmf_paid",
        mode="before",
    )
    @classmethod
    def _strip_numeric_formatting(cls, v):
        return _clean_numeric(v)

    @field_validator("hts_code")
    @classmethod
    def _hts_digits_only(cls, v: str) -> str:
        cleaned = v.replace(".", "").replace(" ", "").strip()
        if not cleaned.isdigit():
            raise ValueError(f"HTS code must be digits (got {v!r})")
        return cleaned

    @field_validator("unit_of_measure")
    @classmethod
    def _uom_upper(cls, v: str) -> str:
        return v.strip().upper()


class Entry7501(BaseModel):
    """A full CBP 7501 entry summary."""

    entry_number: str
    entry_date: date = Field(description="date of importation / entry")
    importer_of_record: str
    port_of_entry: Optional[str] = None
    source_document: Optional[str] = Field(
        default=None, description="filename/source this entry was extracted from"
    )

    line_items: list[LineItem] = Field(min_length=1)

    # Header totals as printed on the form. These are the model's reading of
    # the summary figures — validation.py reconciles them against the sum of
    # the line items. A mismatch is one of the strongest error signals we have.
    total_entered_value: Money = Field(ge=0)
    total_duty: Money = Field(ge=0)
    total_mpf: Money = Field(ge=0, default=Decimal("0"))
    total_hmf: Money = Field(ge=0, default=Decimal("0"))

    @field_validator(
        "total_entered_value", "total_duty", "total_mpf", "total_hmf", mode="before",
    )
    @classmethod
    def _strip_numeric_formatting(cls, v):
        return _clean_numeric(v)

    @property
    def total_duties_taxes_fees(self) -> Money:
        """The pool the 99% drawback is calculated against, per line summed."""
        return sum(
            (li.duty_paid + li.mpf_paid + li.hmf_paid for li in self.line_items),
            Decimal("0"),
        )
