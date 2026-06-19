"""
Export-side schema.

The import side (Entry7501 in schema.py) is only half of a drawback claim. To
match, we need the export universe too: proof that goods left the country (or
were destroyed). This is the second independently-maintained dataset whose
reconciliation against the import side is the hard problem.

Sources in practice: bill of lading, AES/EEI electronic export filing,
commercial invoice for the export sale, proof of export/destruction. We model
the fields matching and the lesser-of cap actually need, with the same
philosophy as the import side: strict types, Decimal money, per-field
provenance, transcribe-don't-compute.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from schema import ExtractionProvenance, Money


class ExportLineItem(BaseModel):
    """A single exported (or destroyed) line."""

    line_number: int = Field(ge=1)
    # HTS is how substitution matching ties export to import. May be absent on
    # some export docs (a BOL often lacks it) — null is allowed and flagged by
    # validation, because substitution can't be done without it.
    hts_code: Optional[str] = Field(
        default=None, description="10-digit HTSUS if available, else null"
    )
    description: str
    quantity: Decimal = Field(gt=0)
    unit_of_measure: str
    # Value of the exported article — used for the lesser-of cap basis and as a
    # sanity signal in matching.
    export_value: Money = Field(ge=0, default=Decimal("0"))

    # Per-unit duty that WOULD be attributable to the exported article, when
    # known. Feeds the substitution lesser-of cap in calculation.py. Often this
    # is derived elsewhere, not read off the export doc, so it's optional here.
    exported_article_duty_per_unit: Optional[Decimal] = None

    provenance: dict[str, ExtractionProvenance] = Field(default_factory=dict)

    @field_validator("hts_code")
    @classmethod
    def _hts_digits_or_none(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.replace(".", "").replace(" ", "").strip()
        if not cleaned:
            return None
        if not cleaned.isdigit():
            raise ValueError(f"HTS code must be digits or null (got {v!r})")
        return cleaned

    @field_validator("unit_of_measure")
    @classmethod
    def _uom_upper(cls, v: str) -> str:
        return v.strip().upper()


class ExportRecord(BaseModel):
    """
    A proof-of-export record. The export-side analogue of Entry7501.

    `is_destruction` flips this between export drawback and destruction
    drawback — both are eligible under 1313(j), with different proof
    requirements, so we carry the flag.
    """

    export_id: str = Field(description="bill of lading / AES ITN / internal ref")
    export_date: date
    exporter: str
    destination_country: Optional[str] = None
    source_document: Optional[str] = Field(
        default=None, description="filename/source this record was extracted from"
    )
    is_destruction: bool = Field(
        default=False, description="True if goods destroyed rather than exported"
    )

    line_items: list[ExportLineItem] = Field(min_length=1)

    total_export_value: Money = Field(ge=0, default=Decimal("0"))
