"""
Generate a realistic, internally-consistent fixture for ACME Q2 2026.

Products: SKU-001 Widget, SKU-002 Gadget, SKU-003 Component
Warehouses: W1 Hamburg, W2 Berlin, W3 Munich (capacity in kg — unit-mismatch trap)
Destinations: D1 Paris, D2 Vienna, D3 Amsterdam
Horizon: Apr, May, Jun 2026

All numbers are feasible: total demand (1,208 t) < total capacity (1,350 t).
"""
from pathlib import Path
import csv

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
)
from reportlab.lib import colors


HERE = Path(__file__).parent
OUT = HERE / "acme_q2_2026"
OUT.mkdir(parents=True, exist_ok=True)


SKUS = ["SKU-001", "SKU-002", "SKU-003"]
WAREHOUSES = [
    ("W1", "Hamburg", 450, "tons"),
    ("W2", "Berlin",  380, "tons"),
    ("W3", "Munich",  520_000, "kg"),   # <-- unit mismatch (520 t equivalent)
]
DESTINATIONS = [
    ("D1", "Paris"),
    ("D2", "Vienna"),
    ("D3", "Amsterdam"),
]

# Monthly demand in TONS by SKU (total = ~1208 t over Q2)
DEMAND_TONS = {
    "Apr": {"SKU-001": 140, "SKU-002": 115, "SKU-003":  125},   # 380
    "May": {"SKU-001": 155, "SKU-002": 120, "SKU-003":  135},   # 410
    "Jun": {"SKU-001": 160, "SKU-002": 125, "SKU-003":  133},   # 418
}

# Destination demand split (fraction of monthly SKU demand shipped to each dest)
DEST_SPLIT = {"D1": 0.40, "D2": 0.35, "D3": 0.25}

# Routing cost EUR/ton by (warehouse, destination, sku)
ROUTING = {
    ("W1", "D1"): {"SKU-001": 42, "SKU-002": 48, "SKU-003": 39},
    ("W1", "D2"): {"SKU-001": 58, "SKU-002": 62, "SKU-003": 55},
    ("W1", "D3"): {"SKU-001": 35, "SKU-002": 40, "SKU-003": 33},
    ("W2", "D1"): {"SKU-001": 55, "SKU-002": 60, "SKU-003": 52},
    ("W2", "D2"): {"SKU-001": 45, "SKU-002": 50, "SKU-003": 43},
    ("W2", "D3"): {"SKU-001": 48, "SKU-002": 53, "SKU-003": 46},
    ("W3", "D1"): {"SKU-001": 62, "SKU-002": 68, "SKU-003": 59},
    ("W3", "D2"): {"SKU-001": 38, "SKU-002": 42, "SKU-003": 36},
    ("W3", "D3"): {"SKU-001": 72, "SKU-002": 78, "SKU-003": 69},
}


# ----------------------------- warehouse_capacity.csv
def write_capacity():
    path = OUT / "warehouse_capacity.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["warehouse_id", "city", "monthly_capacity", "unit"])
        for wid, city, cap, unit in WAREHOUSES:
            w.writerow([wid, city, cap, unit])
    print(f"wrote {path.name} ({path.stat().st_size}B)")


# ----------------------------- routing_matrix.csv
def write_routing():
    path = OUT / "routing_matrix.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["warehouse_id", "destination_id", "sku", "cost_eur_per_ton"])
        for (wid, did), skumap in ROUTING.items():
            for sku, cost in skumap.items():
                w.writerow([wid, did, sku, cost])
    print(f"wrote {path.name} ({path.stat().st_size}B)")


# ----------------------------- demand_forecast_q2.xlsx
def write_demand_xlsx():
    wb = Workbook()
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="1F4E78")
    border = Border(
        left=Side(style="thin", color="CCCCCC"),
        right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),
        bottom=Side(style="thin", color="CCCCCC"),
    )

    def style_header(ws, n_cols):
        for c in ws[1]:
            c.font = header_font
            c.fill = header_fill
            c.alignment = Alignment(horizontal="center")
        for row in ws.iter_rows(min_row=1, max_col=n_cols):
            for c in row:
                c.border = border

    # Monthly sheets
    first = True
    for month in ("Apr", "May", "Jun"):
        ws = wb.active if first else wb.create_sheet()
        first = False
        ws.title = month
        ws.append(["sku", "destination_id", "city", "demand_tons"])
        for sku in SKUS:
            total = DEMAND_TONS[month][sku]
            for did, dcity in DESTINATIONS:
                ws.append([sku, did, dcity, round(total * DEST_SPLIT[did], 2)])
        for col_letter, width in zip("ABCD", (12, 16, 14, 14)):
            ws.column_dimensions[col_letter].width = width
        style_header(ws, 4)

    # Summary sheet
    ws = wb.create_sheet("Summary")
    ws.append(["sku"] + [m for m in ("Apr", "May", "Jun")] + ["Q2_total"])
    for sku in SKUS:
        row = [sku] + [DEMAND_TONS[m][sku] for m in ("Apr", "May", "Jun")]
        row.append(sum(row[1:]))
        ws.append(row)
    # totals row
    totals = ["TOTAL"]
    for m in ("Apr", "May", "Jun"):
        totals.append(sum(DEMAND_TONS[m].values()))
    totals.append(sum(totals[1:]))
    ws.append(totals)
    for col_letter, width in zip("ABCDE", (12, 10, 10, 10, 12)):
        ws.column_dimensions[col_letter].width = width
    style_header(ws, 5)
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True)

    path = OUT / "demand_forecast_q2.xlsx"
    wb.save(path)
    print(f"wrote {path.name} ({path.stat().st_size}B)")


# ----------------------------- union_contract_munich.pdf
def write_union_contract_pdf():
    path = OUT / "union_contract_munich.pdf"
    doc = SimpleDocTemplate(
        str(path), pagesize=A4,
        leftMargin=2.2 * cm, rightMargin=2.2 * cm,
        topMargin=2.2 * cm, bottomMargin=2.2 * cm,
        title="ACME Munich — IG Metall Collective Agreement 2026",
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], spaceAfter=12, textColor=colors.HexColor("#1F4E78"))
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], spaceAfter=8, textColor=colors.HexColor("#1F4E78"))
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10, leading=14, spaceAfter=6)
    small = ParagraphStyle("small", parent=styles["BodyText"], fontSize=8, leading=11, textColor=colors.HexColor("#555555"))

    story = []
    story.append(Paragraph("ACME Logistics GmbH — Munich Distribution Center", h1))
    story.append(Paragraph("Collective Bargaining Agreement (IG Metall, Bayern)", h2))
    story.append(Paragraph("Effective: 01 January 2026 &nbsp;·&nbsp; Expires: 31 December 2027", small))
    story.append(Spacer(1, 10))

    story.append(Paragraph("§1 Scope", h2))
    story.append(Paragraph(
        "This agreement covers all hourly warehouse, picking, packing, and forklift operators employed at "
        "the ACME Munich Distribution Center (Plant code DE-MUC-03). Salaried technical, administrative, "
        "and managerial personnel are excluded.",
        body))

    story.append(Paragraph("§2 Regular Working Hours", h2))
    story.append(Paragraph(
        "The regular shift shall not exceed <b>eight (8) hours</b> per working day, exclusive of the mandatory "
        "unpaid meal break. The weekly working time shall not exceed <b>forty-eight (48) hours</b> averaged over "
        "any rolling four (4) week period. Any planned shift exceeding 8h requires prior written consent from "
        "the Works Council (Betriebsrat).",
        body))

    story.append(Paragraph("§3 Rest Breaks", h2))
    story.append(Paragraph(
        "A paid rest break of <b>30 minutes</b> shall be granted for every shift of six (6) hours or longer. "
        "An additional 15-minute rest break is granted when the total shift length reaches 9 hours "
        "(subject to §4 overtime approval).",
        body))

    story.append(Paragraph("§4 Overtime", h2))
    story.append(Paragraph(
        "Overtime is defined as any time worked in excess of the 8h regular shift defined in §2. Overtime "
        "must be approved in advance by the shift supervisor and reported within 24 hours to payroll.",
        body))
    story.append(Paragraph(
        "Weekday overtime up to two (2) hours per day is compensated at <b>125%</b> of base rate. Any additional "
        "hours beyond the first two are compensated at <b>150%</b>.",
        body))

    story.append(Paragraph("§5 Weekend and Holiday Work", h2))
    story.append(Paragraph(
        "<b>Weekend overtime is prohibited</b> except in the case of a documented operational emergency "
        "(Notfall) declared in writing by a site director or above. Saturday work, when authorised, is "
        "compensated at 150%; Sunday and public-holiday work at 200%. No employee may be scheduled for more "
        "than two (2) consecutive weekends, and the subsequent weekend shall be a guaranteed rest period.",
        body))

    story.append(PageBreak())

    story.append(Paragraph("§6 Night Shift Premium", h2))
    story.append(Paragraph(
        "Hours worked between 22:00 and 06:00 attract a night-shift premium of 25% above base rate, in "
        "addition to any overtime premium under §4. Employees may not be scheduled for more than five (5) "
        "consecutive night shifts without an intervening 48-hour rest period.",
        body))

    story.append(Paragraph("§7 Forklift and Heavy-Equipment Operators", h2))
    story.append(Paragraph(
        "Certified forklift operators shall not operate heavy equipment for more than six (6) consecutive "
        "hours without a mandatory 20-minute rest. A minimum of one certified operator must be on site for "
        "every shift in which pallet movements exceed 50 units.",
        body))

    story.append(Paragraph("§8 Seasonal Staffing and Temporary Labour", h2))
    story.append(Paragraph(
        "Temporary agency labour may not exceed 15% of headcount on any given shift. During peak months "
        "(defined as April–June and October–December), this cap may be raised to 25% with Works Council "
        "approval, provided all temporary staff receive the same base rate as equivalent permanent staff.",
        body))

    story.append(Paragraph("§9 Capacity Reporting", h2))
    story.append(Paragraph(
        "For the purposes of operational reporting, warehouse throughput at the Munich DC shall be measured "
        "in <b>kilograms</b> to match the historical record system (SAP IM-WM module DE-MUC-03 pre-dates the "
        "2023 metric harmonisation and retains kg as its native unit). Reports submitted to central planning "
        "in Frankfurt are automatically converted to tonnes downstream.",
        body))

    story.append(Paragraph("§10 Dispute Resolution", h2))
    story.append(Paragraph(
        "All disputes arising under this agreement shall first be addressed through the Works Council. "
        "Unresolved matters may be escalated to the IG Metall Bayern regional office within 30 calendar days.",
        body))

    story.append(Spacer(1, 18))
    story.append(Paragraph("Signatures", h2))
    sig = Table(
        [
            ["__________________________", "__________________________"],
            ["Stefan Krüger", "Dr. Helga Mayer"],
            ["Plant Director, ACME Munich", "Chair, Works Council (Betriebsrat)"],
            ["", ""],
            ["__________________________", ""],
            ["Klaus Weidmann", ""],
            ["Regional Secretary, IG Metall Bayern", ""],
        ],
        colWidths=[7.5 * cm, 7.5 * cm],
    )
    sig.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(sig)

    doc.build(story)
    print(f"wrote {path.name} ({path.stat().st_size}B)")


# ----------------------------- instructions.txt
def write_instructions():
    path = OUT / "instructions.txt"
    path.write_text(
        "From: planner@acme.com\n"
        "Subject: Q2 2026 distribution plan — Munich, Berlin, Hamburg\n\n"
        "Team,\n\n"
        "Please run the Q2 2026 distribution optimization for our Germany DC network.\n"
        "Objective: minimize total routing cost in EUR across SKU-001/002/003 shipped from\n"
        "warehouses W1 (Hamburg), W2 (Berlin), W3 (Munich) to destinations D1 (Paris),\n"
        "D2 (Vienna), D3 (Amsterdam).\n\n"
        "Constraints:\n"
        "  - Monthly warehouse capacities per the attached capacity CSV.\n"
        "  - Monthly SKU demand per the attached XLSX (tabs Apr / May / Jun; Summary is informational).\n"
        "  - Munich labour rules per the attached IG Metall collective agreement. In particular:\n"
        "      * 8h shift cap (§2), weekend overtime prohibited except documented Notfall (§5).\n"
        "      * Prefer Munich (W3) for SKU-001 where routing cost is competitive.\n"
        "  - All demand must be fully satisfied (no backorders).\n\n"
        "Deliverable: optimal shipment plan by warehouse × destination × SKU × month,\n"
        "plus total cost and per-warehouse utilization.\n\n"
        "— Planner\n",
        encoding="utf-8",
    )
    print(f"wrote {path.name} ({path.stat().st_size}B)")


def main():
    write_capacity()
    write_routing()
    write_demand_xlsx()
    write_union_contract_pdf()
    write_instructions()
    print(f"\nfixtures in: {OUT}")


if __name__ == "__main__":
    main()
