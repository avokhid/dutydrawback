"""
End-to-end pipeline demo: documents -> validate -> match -> designate ->
calculate refund, with review routing.

Runs entirely on hand-built verified objects (no API/PDF needed) to show the
whole flow joining up. This is the thin end-to-end line the MVP is built around.

Run: python3 demo_pipeline.py
"""

from datetime import date
from decimal import Decimal

from schema import Entry7501, LineItem
from export_schema import ExportRecord, ExportLineItem
from validation import validate_entry
from export_validation import validate_export
from matching import MatchingEngine, MatchConfig, UomTable, MatchTier, to_designations
from inventory import AccountingMethod
from calculation import calculate_claim, DrawbackType


def build_imports():
    return [
        Entry7501(
            entry_number="ENT-1001", entry_date=date(2024, 3, 11),
            importer_of_record="Acme Imports LLC",
            source_document="entry_summary_7501.pdf",
            line_items=[
                LineItem(line_number=1, hts_code="8471.30.0100",
                         description="Portable laptop computer", quantity=Decimal("1000"),
                         unit_of_measure="EA", unit_price=Decimal("200.00"),
                         entered_value=Decimal("200000.00"),
                         duty_paid=Decimal("4500.00"), mpf_paid=Decimal("500.00")),
            ],
            total_entered_value=Decimal("200000.00"),
            total_duty=Decimal("4500.00"), total_mpf=Decimal("500.00"),
        ),
    ]


def build_exports():
    return [
        ExportRecord(
            export_id="BOL-77", export_date=date(2025, 2, 1), exporter="Acme",
            source_document="export_bol_77.pdf",
            line_items=[
                ExportLineItem(line_number=1, hts_code="8471.30.0100",
                               description="Laptop computer unit",
                               quantity=Decimal("60"), unit_of_measure="CTN",
                               exported_article_duty_per_unit=Decimal("5.00")),
            ],
        ),
    ]


def main():
    imports = build_imports()
    exports = build_exports()

    print("=== Step 1: validate both sides ===")
    for e in imports:
        r = validate_entry(e, claim_date=date(2025, 9, 2))
        print(f"  import {e.entry_number}: {'OK' if r.ok else 'GATED'}"
              f" ({len(r.findings)} findings)")
    for x in exports:
        r = validate_export(x)
        print(f"  export {x.export_id}: {'OK' if r.ok else 'GATED'}"
              f" ({len(r.findings)} findings)")

    print("\n=== Step 2: match (1 carton = 10 each) ===")
    uom = UomTable()
    uom.add("CTN", "EA", Decimal("10"))
    engine = MatchingEngine(MatchConfig(
        method=AccountingMethod.FIFO, uom=uom,
        auto_pass_threshold=Decimal("0.90"), review_threshold=Decimal("0.50"),
    ))
    matches = engine.match(imports, exports)
    for m in matches:
        print(f"  {m.entry_number} L{m.import_line_number} -> {m.export_id}: "
              f"{m.matched_quantity} EA, confidence {m.confidence:.2f}, tier {m.tier.value}")
        for n in m.notes:
            print(f"      note: {n}")

    print("\n=== Step 3: designate auto-pass matches & calculate ===")
    designations = to_designations(matches, exports,
                                   drawback_type=DrawbackType.UNUSED_SUBSTITUTION)
    if not designations:
        print("  no auto-pass designations; all matches routed to review")
        # for the demo, include review-tier provisionally to show a number
        designations = to_designations(matches, exports,
                                       drawback_type=DrawbackType.UNUSED_SUBSTITUTION,
                                       include_review_tier=True)
        print("  (showing provisional estimate including review-tier matches)")
    claim = calculate_claim({e.entry_number: e for e in imports}, designations)
    print(claim.summary())

    review = [m for m in matches if m.tier is MatchTier.REVIEW]
    print(f"\n=== Routing summary ===")
    print(f"  matches proposed: {len(matches)}")
    print(f"  auto-pass: {sum(1 for m in matches if m.tier is MatchTier.AUTO_PASS)}")
    print(f"  to review: {len(review)}")


if __name__ == "__main__":
    main()
