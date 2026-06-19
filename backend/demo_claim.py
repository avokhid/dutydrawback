"""Demo claim data: imports, exports, and matching for the reviewer UI."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from schema import Entry7501, LineItem
from export_schema import ExportRecord, ExportLineItem
from inventory import AccountingMethod
from matching import MatchingEngine, MatchConfig, UomTable


def build_demo_entries() -> list[Entry7501]:
    def line(n, hts, desc, qty, uom, duty, mpf=Decimal("0")):
        price = Decimal("200.00")
        return LineItem(
            line_number=n,
            hts_code=hts,
            description=desc,
            quantity=Decimal(qty),
            unit_of_measure=uom,
            unit_price=price,
            entered_value=Decimal(qty) * price,
            duty_paid=Decimal(duty),
            mpf_paid=Decimal(mpf),
        )

    return [
        Entry7501(
            entry_number="ENT-1001",
            entry_date=date(2024, 3, 11),
            importer_of_record="Acme Imports LLC",
            line_items=[
                line(1, "8471.30.0100", "WIDGET-A laptop unit", "500", "EA", "4500", "500"),
                line(2, "8544.42.9090", "USB-C cable", "2000", "EA", "182", "25"),
                line(3, "8504.40.9510", "65W adapter", "800", "EA", "320", "40"),
            ],
            total_entered_value=Decimal("556000.00"),
            total_duty=Decimal("5002.00"),
            total_mpf=Decimal("565.00"),
        ),
        Entry7501(
            entry_number="ENT-1002",
            entry_date=date(2024, 4, 2),
            importer_of_record="Acme Imports LLC",
            line_items=[
                line(1, "8471.30.0100", "WIDGET-B tablet unit", "350", "EA", "2800", "35"),
                line(2, "4202.92.9100", "13in laptop sleeve", "1200", "EA", "96", "12"),
                line(3, "8471.60.2000", "Wireless mouse", "1500", "EA", "75", "10"),
            ],
            total_entered_value=Decimal("310000.00"),
            total_duty=Decimal("2971.00"),
            total_mpf=Decimal("57.00"),
        ),
        Entry7501(
            entry_number="ENT-1003",
            entry_date=date(2024, 5, 15),
            importer_of_record="Acme Imports LLC",
            line_items=[
                line(1, "8471.30.0100", "WIDGET-A laptop unit", "500", "CTN", "4500", "500"),
                line(2, "8504.40.9510", "ADPT-90W power supply", "300", "EA", "180", "20"),
                line(3, "4202.92.9100", "CASE-15IN sleeve", "900", "EA", "90", "9"),
            ],
            total_entered_value=Decimal("256000.00"),
            total_duty=Decimal("4770.00"),
            total_mpf=Decimal("529.00"),
        ),
    ]


def build_demo_exports() -> list[ExportRecord]:
    def exp_line(n, hts, desc, qty, uom, duty_per_unit=None):
        return ExportLineItem(
            line_number=n,
            hts_code=hts,
            description=desc,
            quantity=Decimal(qty),
            unit_of_measure=uom,
            export_value=Decimal(qty) * Decimal("200"),
            exported_article_duty_per_unit=Decimal(duty_per_unit) if duty_per_unit else None,
        )

    return [
        ExportRecord(
            export_id="BOL-77",
            export_date=date(2025, 2, 1),
            exporter="Acme",
            line_items=[
                exp_line(1, "8471.30.0100", "Laptop computer unit", "500", "EA", "5.00"),
                exp_line(2, "8544.42.9090", "USB-C cable", "2000", "EA", "0.09"),
                exp_line(3, "8504.40.9510", "65W adapter", "800", "EA", "0.40"),
            ],
        ),
        ExportRecord(
            export_id="BOL-88",
            export_date=date(2025, 3, 10),
            exporter="Acme",
            line_items=[
                exp_line(1, "8471.30.0100", "Tablet unit", "350", "EA", "8.00"),
                exp_line(2, "4202.92.9100", "13in sleeve", "1200", "EA", "0.08"),
                exp_line(3, "8471.60.2000", "Wireless mouse", "1500", "EA", "0.05"),
            ],
        ),
        ExportRecord(
            export_id="BOL-99",
            export_date=date(2025, 9, 2),
            exporter="Acme",
            line_items=[
                exp_line(1, "8471.30.0100", "Laptop assembly, blue", "6000", "EA", "5.00"),
                exp_line(2, "8504.40.9510", "AC adapter, generic", "300", "EA", "0.60"),
                exp_line(3, "4202.92.9100", "15in laptop sleeve", "900", "EA", "0.10"),
            ],
        ),
    ]


def run_demo_matching():
    uom = UomTable()
    uom.add("CTN", "EA", Decimal("10"))
    entries = build_demo_entries()
    exports = build_demo_exports()
    engine = MatchingEngine(
        MatchConfig(
            method=AccountingMethod.FIFO,
            uom=uom,
            auto_pass_threshold=Decimal("0.90"),
            review_threshold=Decimal("0.50"),
        )
    )
    matches = engine.match(entries, exports)
    return entries, exports, matches
