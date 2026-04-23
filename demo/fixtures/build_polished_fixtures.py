"""
Polished demo fixture generator for ACME Logistics Q2 2026.

This script produces enterprise-grade-looking versions of the demo fixtures
while preserving every number and every clause verbatim from the canonical
source (demo/fixtures/build_acme_q2_2026.py).

Outputs written to: ./acme_q2_2026/
  - warehouse_capacity.csv          (unchanged — W3 stays in kg)
  - routing_matrix.csv              (unchanged)
  - demand_forecast_q2.xlsx         (styled, 4 sheets incl. Summary + chart)
  - union_contract_munich.pdf       (cover + styled body + signature page)
  - instructions.txt                (Outlook email format)
  - cover_sheet.pdf                 (routing cover sheet, bonus)
"""
from pathlib import Path
import csv

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side, NamedStyle
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.utils import get_column_letter

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, BaseDocTemplate, PageTemplate, Frame,
    Paragraph, Spacer, PageBreak, Table, TableStyle, Image, KeepTogether,
    HRFlowable, Flowable,
)
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing, Circle, Rect, String, Line, Polygon
from reportlab.graphics import renderPDF


# =========================================================================
# PATHS
# =========================================================================
HERE = Path(__file__).parent
OUT = HERE / "acme_q2_2026"
OUT.mkdir(parents=True, exist_ok=True)


# =========================================================================
# CANONICAL DATA — copied verbatim from build_acme_q2_2026.py
# =========================================================================
SKUS = ["SKU-001", "SKU-002", "SKU-003"]

WAREHOUSES = [
    ("W1", "Hamburg", 450, "tons"),
    ("W2", "Berlin",  380, "tons"),
    ("W3", "Munich",  520_000, "kg"),   # unit mismatch — intentional
]

DESTINATIONS = [
    ("D1", "Paris"),
    ("D2", "Vienna"),
    ("D3", "Amsterdam"),
]

DEMAND_TONS = {
    "Apr": {"SKU-001": 140, "SKU-002": 115, "SKU-003": 125},   # 380
    "May": {"SKU-001": 155, "SKU-002": 120, "SKU-003": 135},   # 410
    "Jun": {"SKU-001": 160, "SKU-002": 125, "SKU-003": 133},   # 418
}

DEST_SPLIT = {"D1": 0.40, "D2": 0.35, "D3": 0.25}

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


# =========================================================================
# BRAND TOKENS
# =========================================================================
ACME_BLUE = "1F4E78"
ACME_BLUE_HEX = colors.HexColor("#1F4E78")
ACME_BLUE_LIGHT = colors.HexColor("#D9E4F1")
ACME_GOLD = colors.HexColor("#BF9000")
ACME_RED = colors.HexColor("#B22222")
PAPER = colors.HexColor("#FDFCF7")
RULE_GRAY = colors.HexColor("#B8B8B8")
SOFT_GRAY = colors.HexColor("#6A6A6A")
BAND_GRAY = "F2F2F2"


# =========================================================================
# 1. warehouse_capacity.csv  (unchanged)
# =========================================================================
def write_capacity():
    path = OUT / "warehouse_capacity.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["warehouse_id", "city", "monthly_capacity", "unit"])
        for wid, city, cap, unit in WAREHOUSES:
            w.writerow([wid, city, cap, unit])
    print(f"  ✓ {path.name}  ({path.stat().st_size}B)")


# =========================================================================
# 2. routing_matrix.csv  (unchanged)
# =========================================================================
def write_routing():
    path = OUT / "routing_matrix.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["warehouse_id", "destination_id", "sku", "cost_eur_per_ton"])
        for (wid, did), skumap in ROUTING.items():
            for sku, cost in skumap.items():
                w.writerow([wid, did, sku, cost])
    print(f"  ✓ {path.name}  ({path.stat().st_size}B)")


# =========================================================================
# 3. demand_forecast_q2.xlsx  (polished)
# =========================================================================
def write_demand_xlsx():
    wb = Workbook()

    # --- shared styles ------------------------------------------------------
    title_font = Font(name="Calibri", bold=True, size=14, color="FFFFFF")
    subtitle_font = Font(name="Calibri", italic=True, size=9, color="FFFFFF")
    header_font = Font(name="Calibri", bold=True, size=11, color="FFFFFF")
    body_font = Font(name="Calibri", size=10)
    body_bold = Font(name="Calibri", size=10, bold=True)
    total_font = Font(name="Calibri", bold=True, size=11, color="FFFFFF")
    note_font = Font(name="Calibri", size=9, italic=True, color="6A6A6A")

    title_fill = PatternFill("solid", fgColor=ACME_BLUE)
    subtitle_fill = PatternFill("solid", fgColor="2E6DA4")
    header_fill = PatternFill("solid", fgColor=ACME_BLUE)
    band_fill = PatternFill("solid", fgColor=BAND_GRAY)
    total_fill = PatternFill("solid", fgColor=ACME_BLUE)

    thin = Side(style="thin", color="CCCCCC")
    med = Side(style="medium", color=ACME_BLUE)
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    center = Alignment(horizontal="center", vertical="center")
    left = Alignment(horizontal="left", vertical="center", indent=1)
    right = Alignment(horizontal="right", vertical="center")

    def style_month_sheet(ws, month_label):
        # Title row
        ws.merge_cells("A1:D1")
        ws["A1"] = f"ACME Logistics GmbH  —  Q2 2026 Demand Forecast  —  {month_label}"
        ws["A1"].font = title_font
        ws["A1"].fill = title_fill
        ws["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
        ws.row_dimensions[1].height = 26

        # Subtitle row
        ws.merge_cells("A2:D2")
        ws["A2"] = "Prepared by: S&OP Planning, Munich HQ    •    Revision 3    •    CONFIDENTIAL — Internal Use Only"
        ws["A2"].font = subtitle_font
        ws["A2"].fill = subtitle_fill
        ws["A2"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
        ws.row_dimensions[2].height = 16

        # Header row (row 3)
        headers = ["SKU", "Destination ID", "City", "Demand (tons)"]
        for i, h in enumerate(headers, start=1):
            c = ws.cell(row=3, column=i, value=h)
            c.font = header_font
            c.fill = header_fill
            c.alignment = center
            c.border = border
        ws.row_dimensions[3].height = 22
        ws.freeze_panes = "A4"

    def fill_month(ws, month_label):
        style_month_sheet(ws, month_label)
        row = 4
        total = 0.0
        for sku in SKUS:
            monthly_total = DEMAND_TONS[month_label][sku]
            for did, dcity in DESTINATIONS:
                val = round(monthly_total * DEST_SPLIT[did], 2)
                total += val
                ws.cell(row=row, column=1, value=sku).font = body_bold
                ws.cell(row=row, column=2, value=did).font = body_font
                ws.cell(row=row, column=3, value=dcity).font = body_font
                cell_val = ws.cell(row=row, column=4, value=val)
                cell_val.font = body_font
                cell_val.number_format = "#,##0.00"
                for col in range(1, 5):
                    c = ws.cell(row=row, column=col)
                    c.border = border
                    if (row % 2) == 0:
                        c.fill = band_fill
                ws.cell(row=row, column=1).alignment = left
                ws.cell(row=row, column=2).alignment = center
                ws.cell(row=row, column=3).alignment = left
                ws.cell(row=row, column=4).alignment = right
                row += 1

        # Total row
        ws.cell(row=row, column=1, value=f"TOTAL {month_label}").font = total_font
        ws.cell(row=row, column=1).fill = total_fill
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=3)
        ws.cell(row=row, column=1).alignment = left
        tcell = ws.cell(row=row, column=4, value=total)
        tcell.font = total_font
        tcell.fill = total_fill
        tcell.alignment = right
        tcell.number_format = "#,##0.00"
        for col in range(1, 5):
            ws.cell(row=row, column=col).border = Border(top=med, bottom=med, left=thin, right=thin)

        # Column widths
        for col_letter, width in zip("ABCD", (14, 16, 16, 18)):
            ws.column_dimensions[col_letter].width = width

    # Monthly sheets
    first = True
    for month in ("Apr", "May", "Jun"):
        ws = wb.active if first else wb.create_sheet()
        first = False
        ws.title = month
        fill_month(ws, month)

    # --- Summary sheet ------------------------------------------------------
    ws = wb.create_sheet("Summary")

    ws.merge_cells("A1:F1")
    ws["A1"] = "ACME Logistics GmbH  —  Q2 2026 Demand Forecast  —  Summary"
    ws["A1"].font = title_font
    ws["A1"].fill = title_fill
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 26

    ws.merge_cells("A2:F2")
    ws["A2"] = "Prepared by: S&OP Planning, Munich HQ    •    Revision 3    •    CONFIDENTIAL — Internal Use Only"
    ws["A2"].font = subtitle_font
    ws["A2"].fill = subtitle_fill
    ws["A2"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[2].height = 16

    # Header row
    summary_headers = ["SKU", "Apr", "May", "Jun", "Q2 Total", "Notes"]
    for i, h in enumerate(summary_headers, start=1):
        c = ws.cell(row=3, column=i, value=h)
        c.font = header_font
        c.fill = header_fill
        c.alignment = center
        c.border = border
    ws.row_dimensions[3].height = 22
    ws.freeze_panes = "A4"

    notes_map = {
        "SKU-001": "Focus item — Munich preferred routing where cost-effective",
        "SKU-002": "Standard distribution — maintain current warehouse mix",
        "SKU-003": "Standard distribution — monitor Hamburg capacity",
    }

    for idx, sku in enumerate(SKUS):
        r = 4 + idx
        ws.cell(row=r, column=1, value=sku).font = body_bold
        ws.cell(row=r, column=1).alignment = left
        for j, m in enumerate(("Apr", "May", "Jun"), start=2):
            c = ws.cell(row=r, column=j, value=DEMAND_TONS[m][sku])
            c.font = body_font
            c.alignment = right
            c.number_format = "#,##0"
        # Q2 total as a formula so it stays dynamic
        total_cell = ws.cell(row=r, column=5, value=f"=SUM(B{r}:D{r})")
        total_cell.font = body_bold
        total_cell.alignment = right
        total_cell.number_format = "#,##0"
        notes_cell = ws.cell(row=r, column=6, value=notes_map[sku])
        notes_cell.font = note_font
        notes_cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True, indent=1)

        for col in range(1, 7):
            c = ws.cell(row=r, column=col)
            c.border = border
            if (r % 2) == 0:
                c.fill = band_fill

    # Totals row
    total_row = 4 + len(SKUS)
    ws.cell(row=total_row, column=1, value="TOTAL").font = total_font
    ws.cell(row=total_row, column=1).fill = total_fill
    ws.cell(row=total_row, column=1).alignment = left
    for j, col_letter in enumerate(("B", "C", "D", "E"), start=2):
        # Bottom totals use formulas too
        first_data = 4
        last_data = total_row - 1
        formula = f"=SUM({col_letter}{first_data}:{col_letter}{last_data})"
        c = ws.cell(row=total_row, column=j, value=formula)
        c.font = total_font
        c.fill = total_fill
        c.alignment = right
        c.number_format = "#,##0"
    ws.cell(row=total_row, column=6, value="")
    ws.cell(row=total_row, column=6).fill = total_fill
    for col in range(1, 7):
        ws.cell(row=total_row, column=col).border = Border(top=med, bottom=med, left=thin, right=thin)

    # Column widths
    widths = {"A": 12, "B": 10, "C": 10, "D": 10, "E": 12, "F": 56}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w

    # --- Bar chart of Q2 totals by SKU (bottom-right) -----------------------
    chart = BarChart()
    chart.type = "col"
    chart.style = 11
    chart.title = "Q2 2026 Demand (tons) by SKU"
    chart.y_axis.title = "Tons"
    chart.x_axis.title = "SKU"
    data_ref = Reference(ws, min_col=5, min_row=3, max_row=3 + len(SKUS), max_col=5)
    cats_ref = Reference(ws, min_col=1, min_row=4, max_row=3 + len(SKUS))
    chart.add_data(data_ref, titles_from_data=True)
    chart.set_categories(cats_ref)
    chart.dataLabels = DataLabelList(showVal=True)
    chart.height = 8
    chart.width = 14
    # Position bottom-right — row below total, starting at column H
    chart_anchor = f"H3"
    ws.add_chart(chart, chart_anchor)

    # Footer note
    footer_row = total_row + 3
    ws.merge_cells(start_row=footer_row, start_column=1, end_row=footer_row, end_column=6)
    ws.cell(
        row=footer_row,
        column=1,
        value=(
            "Source: ACME S&OP consensus forecast, approved 17 Apr 2026  |  "
            "Forecast horizon: 1 Apr – 30 Jun 2026  |  "
            "Destination split: D1 Paris 40%, D2 Vienna 35%, D3 Amsterdam 25%  |  "
            "Document ID: SOP-Q2-2026-R3"
        ),
    ).font = note_font
    ws.cell(row=footer_row, column=1).alignment = Alignment(horizontal="left", vertical="center", wrap_text=True, indent=1)
    ws.row_dimensions[footer_row].height = 30

    # File-level metadata
    wb.properties.title = "Q2 2026 Demand Forecast"
    wb.properties.creator = "ACME Logistics GmbH — S&OP Planning"
    wb.properties.subject = "Quarterly demand forecast, Q2 2026, Germany DC network"
    wb.properties.keywords = "demand forecast, Q2 2026, ACME, Germany, distribution"
    wb.properties.company = "ACME Logistics GmbH"

    path = OUT / "demand_forecast_q2.xlsx"
    wb.save(path)
    print(f"  ✓ {path.name}  ({path.stat().st_size}B)")


# =========================================================================
# 4. union_contract_munich.pdf  (polished, clause text verbatim)
# =========================================================================
def _confidential_watermark(canv, doc):
    """Diagonal pale-gray CONFIDENTIAL watermark, drawn under all content."""
    canv.saveState()
    canv.setFont("Helvetica-Bold", 90)
    canv.setFillColor(colors.HexColor("#E8E2D4"))
    canv.translate(A4[0] / 2, A4[1] / 2)
    canv.rotate(45)
    canv.drawCentredString(0, 0, "CONFIDENTIAL")
    canv.restoreState()


def _body_page_frame(canv, doc):
    """Header + footer + watermark on every body page."""
    # Warm paper background
    canv.saveState()
    canv.setFillColor(PAPER)
    canv.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    canv.restoreState()

    _confidential_watermark(canv, doc)

    # Top ruled header
    canv.saveState()
    # Left: mini ACME wordmark
    canv.setFont("Helvetica-Bold", 10)
    canv.setFillColor(ACME_BLUE_HEX)
    canv.drawString(2.2 * cm, A4[1] - 1.4 * cm, "ACME")
    canv.setFont("Helvetica", 8)
    canv.setFillColor(SOFT_GRAY)
    canv.drawString(2.2 * cm + 1.4 * cm, A4[1] - 1.4 * cm, "Logistics GmbH")

    # Center: document title
    canv.setFont("Helvetica", 8)
    canv.setFillColor(SOFT_GRAY)
    canv.drawCentredString(
        A4[0] / 2,
        A4[1] - 1.4 * cm,
        "Collective Bargaining Agreement — ACME Munich DC",
    )

    # Right: page X of N
    canv.drawRightString(
        A4[0] - 2.2 * cm,
        A4[1] - 1.4 * cm,
        f"Page {doc.page}",
    )

    # Header rule
    canv.setStrokeColor(RULE_GRAY)
    canv.setLineWidth(0.4)
    canv.line(2.2 * cm, A4[1] - 1.55 * cm, A4[0] - 2.2 * cm, A4[1] - 1.55 * cm)

    # Footer
    canv.setFont("Helvetica", 7.5)
    canv.setFillColor(SOFT_GRAY)
    canv.drawString(
        2.2 * cm,
        1.2 * cm,
        "BV-MUC-2026-003  •  Effective 2026-01-01  •  IG Metall Bayern × ACME Logistics GmbH",
    )
    canv.drawRightString(
        A4[0] - 2.2 * cm,
        1.2 * cm,
        "CONFIDENTIAL — Not for External Distribution",
    )
    # Footer rule
    canv.setStrokeColor(RULE_GRAY)
    canv.setLineWidth(0.4)
    canv.line(2.2 * cm, 1.45 * cm, A4[0] - 2.2 * cm, 1.45 * cm)
    canv.restoreState()


def _cover_page_frame(canv, doc):
    """Paper background + watermark for the cover page."""
    canv.saveState()
    canv.setFillColor(PAPER)
    canv.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    canv.restoreState()
    _confidential_watermark(canv, doc)


def _draw_acme_logo(canv, x, y, scale=1.0):
    """Blue geometric mark + wordmark, drawn on a canvas."""
    canv.saveState()
    canv.translate(x, y)
    canv.scale(scale, scale)
    # Geometric diamond / stacked chevrons mark
    canv.setFillColor(ACME_BLUE_HEX)
    canv.setStrokeColor(ACME_BLUE_HEX)
    # Chevron 1
    p = canv.beginPath()
    p.moveTo(0, 12)
    p.lineTo(10, 22)
    p.lineTo(20, 12)
    p.lineTo(16, 12)
    p.lineTo(10, 18)
    p.lineTo(4, 12)
    p.close()
    canv.drawPath(p, fill=1, stroke=0)
    # Chevron 2
    p = canv.beginPath()
    p.moveTo(0, 4)
    p.lineTo(10, 14)
    p.lineTo(20, 4)
    p.lineTo(16, 4)
    p.lineTo(10, 10)
    p.lineTo(4, 4)
    p.close()
    canv.drawPath(p, fill=1, stroke=0)
    # Wordmark
    canv.setFont("Helvetica-Bold", 18)
    canv.setFillColor(ACME_BLUE_HEX)
    canv.drawString(26, 8, "ACME")
    canv.setFont("Helvetica", 10)
    canv.setFillColor(SOFT_GRAY)
    canv.drawString(26, -5, "Logistics GmbH")
    canv.restoreState()


def _draw_igmetall_logo(canv, x, y, scale=1.0):
    """Red/black wordmark for IG Metall."""
    canv.saveState()
    canv.translate(x, y)
    canv.scale(scale, scale)
    # Red square
    canv.setFillColor(ACME_RED)
    canv.rect(0, 0, 22, 22, fill=1, stroke=0)
    canv.setFillColor(colors.white)
    canv.setFont("Helvetica-Bold", 16)
    canv.drawCentredString(11, 5, "IG")
    # Black wordmark
    canv.setFillColor(colors.black)
    canv.setFont("Helvetica-Bold", 18)
    canv.drawString(28, 8, "IG Metall")
    canv.setFont("Helvetica", 9)
    canv.setFillColor(SOFT_GRAY)
    canv.drawString(28, -4, "Bezirk Bayern")
    canv.restoreState()


def _draw_signature(canv, x, y, seed):
    """Faint hand-drawn-style signature. `seed` varies the shape per signer."""
    canv.saveState()
    canv.setStrokeColor(colors.HexColor("#1B3A66"))
    canv.setLineWidth(1.2)
    p = canv.beginPath()
    p.moveTo(x, y)
    # Simple procedural squiggle
    import math
    steps = 80
    width = 120
    for i in range(steps + 1):
        t = i / steps
        dx = x + t * width
        dy = (
            y
            + 8 * math.sin(t * 7 + seed * 0.9)
            + 4 * math.sin(t * 13 + seed * 1.7)
            + (seed % 3) * math.sin(t * 3)
        )
        if i == 0:
            p.moveTo(dx, dy)
        else:
            p.lineTo(dx, dy)
    canv.drawPath(p, fill=0, stroke=1)
    # Ending flourish
    canv.setLineWidth(0.8)
    canv.line(x + width, y - 2, x + width + 18, y + 6)
    canv.restoreState()


def _draw_signed_stamp(canv, x, y, date_str, initials):
    """Blue circular 'signed' stamp."""
    canv.saveState()
    canv.setStrokeColor(ACME_BLUE_HEX)
    canv.setFillColor(colors.white)
    canv.setLineWidth(1.2)
    # Outer circle
    canv.circle(x, y, 32, stroke=1, fill=0)
    # Inner circle
    canv.setLineWidth(0.6)
    canv.circle(x, y, 26, stroke=1, fill=0)
    # Text
    canv.setFillColor(ACME_BLUE_HEX)
    canv.setFont("Helvetica-Bold", 7)
    # Upper arc text (approximate)
    canv.drawCentredString(x, y + 17, "SIGNED")
    canv.setFont("Helvetica-Bold", 10)
    canv.drawCentredString(x, y + 3, initials)
    canv.setFont("Helvetica", 7)
    canv.drawCentredString(x, y - 8, date_str)
    canv.setFont("Helvetica-Bold", 6)
    canv.drawCentredString(x, y - 18, "BV-MUC-2026")
    canv.restoreState()


def _draw_barcode(canv, x, y, width=180, height=32):
    """Fake linear barcode — alternating bars of varying widths."""
    canv.saveState()
    canv.setFillColor(colors.black)
    # Deterministic pattern
    pattern = [1, 2, 1, 3, 1, 1, 2, 1, 4, 1, 2, 1, 1, 3, 1, 2, 1, 1, 4, 1, 2, 1, 3, 1, 1, 2, 1, 2, 1, 3]
    total_units = sum(pattern) + len(pattern)  # bars + gaps
    unit = width / total_units
    cursor = x
    for i, bar in enumerate(pattern):
        bw = bar * unit
        canv.rect(cursor, y, bw, height, fill=1, stroke=0)
        cursor += bw + unit  # gap
    canv.restoreState()
    canv.saveState()
    canv.setFillColor(colors.black)
    canv.setFont("Helvetica", 7)
    canv.drawCentredString(x + width / 2, y - 9, "BV-MUC-2026-003")
    canv.restoreState()


def _cover_page_content(canv, doc):
    """Everything on the cover page, painted directly on the canvas."""
    _cover_page_frame(canv, doc)

    # Top logos
    _draw_acme_logo(canv, 2.5 * cm, A4[1] - 3.0 * cm, scale=1.3)
    _draw_igmetall_logo(canv, A4[0] - 7.0 * cm, A4[1] - 3.0 * cm, scale=1.2)

    # Divider rule
    canv.setStrokeColor(ACME_BLUE_HEX)
    canv.setLineWidth(1.5)
    canv.line(2.5 * cm, A4[1] - 4.2 * cm, A4[0] - 2.5 * cm, A4[1] - 4.2 * cm)
    canv.setLineWidth(0.5)
    canv.line(2.5 * cm, A4[1] - 4.35 * cm, A4[0] - 2.5 * cm, A4[1] - 4.35 * cm)

    # Eyebrow
    canv.setFillColor(SOFT_GRAY)
    canv.setFont("Helvetica", 10)
    canv.drawCentredString(
        A4[0] / 2,
        A4[1] - 6.5 * cm,
        "BETRIEBSVEREINBARUNG  /  COLLECTIVE BARGAINING AGREEMENT",
    )

    # Main title
    canv.setFillColor(ACME_BLUE_HEX)
    canv.setFont("Helvetica-Bold", 22)
    canv.drawCentredString(
        A4[0] / 2,
        A4[1] - 8.4 * cm,
        "ACME Munich Distribution Center",
    )

    # Subtitle
    canv.setFont("Helvetica-Bold", 14)
    canv.setFillColor(colors.black)
    canv.drawCentredString(
        A4[0] / 2,
        A4[1] - 9.6 * cm,
        "Working Conditions, Overtime, and Capacity Reporting",
    )

    # "Between" block
    canv.setFont("Helvetica", 11)
    canv.setFillColor(colors.black)
    canv.drawCentredString(A4[0] / 2, A4[1] - 12.0 * cm, "Between")
    canv.setFont("Helvetica-Bold", 12)
    canv.drawCentredString(A4[0] / 2, A4[1] - 12.7 * cm, "ACME Logistics GmbH")
    canv.setFont("Helvetica", 10)
    canv.setFillColor(SOFT_GRAY)
    canv.drawCentredString(
        A4[0] / 2,
        A4[1] - 13.3 * cm,
        "Hansastraße 42, 80686 München, Deutschland",
    )

    canv.setFont("Helvetica", 11)
    canv.setFillColor(colors.black)
    canv.drawCentredString(A4[0] / 2, A4[1] - 14.4 * cm, "and")
    canv.setFont("Helvetica-Bold", 12)
    canv.drawCentredString(A4[0] / 2, A4[1] - 15.1 * cm, "IG Metall Bayern")
    canv.setFont("Helvetica", 10)
    canv.setFillColor(SOFT_GRAY)
    canv.drawCentredString(
        A4[0] / 2,
        A4[1] - 15.7 * cm,
        "Bezirksleitung Bayern, Schwanthalerstraße 64, 80336 München",
    )

    # Facts panel
    panel_y = 4.4 * cm
    panel_h = 4.8 * cm
    panel_x = 3.5 * cm
    panel_w = A4[0] - 7.0 * cm
    canv.setFillColor(colors.HexColor("#F5F0E4"))
    canv.setStrokeColor(ACME_BLUE_HEX)
    canv.setLineWidth(0.8)
    canv.roundRect(panel_x, panel_y, panel_w, panel_h, 6, stroke=1, fill=1)

    canv.setFont("Helvetica-Bold", 9)
    canv.setFillColor(SOFT_GRAY)
    canv.drawString(panel_x + 0.6 * cm, panel_y + panel_h - 0.8 * cm, "DOCUMENT CONTROL")

    facts = [
        ("Reference No.", "BV-MUC-2026-003"),
        ("Effective", "01 January 2026"),
        ("Expires", "31 December 2027"),
        ("Scope", "ACME Munich Distribution Center (Plant DE-MUC-03)"),
        ("Revision", "Rev. 3 — Approved 18 December 2025"),
        ("Classification", "Confidential — Internal & IG Metall Works Council"),
    ]
    y = panel_y + panel_h - 1.4 * cm
    for k, v in facts:
        canv.setFont("Helvetica-Bold", 9)
        canv.setFillColor(ACME_BLUE_HEX)
        canv.drawString(panel_x + 0.6 * cm, y, k)
        canv.setFont("Helvetica", 9)
        canv.setFillColor(colors.black)
        canv.drawString(panel_x + 4.6 * cm, y, v)
        y -= 0.55 * cm

    # Bottom note
    canv.setFont("Helvetica-Oblique", 8)
    canv.setFillColor(SOFT_GRAY)
    canv.drawCentredString(
        A4[0] / 2,
        2.2 * cm,
        "This document forms part of the 2026–2027 collective agreement between the signatories listed above.",
    )
    canv.drawCentredString(
        A4[0] / 2,
        1.7 * cm,
        "Unauthorised reproduction or distribution is prohibited.",
    )


def _signature_page_content(canv, doc):
    """Painted directly after Platypus content on the signature page."""
    # Handled via PageTemplate — decoration is drawn before flowables.
    pass


class SignatureBlock(Flowable):
    """Inline Flowable that draws the full signature layout as one unit:
    signature lines, hand-drawn squiggles, names, titles, dates, and stamps.
    Using a custom Flowable means positions are determined by layout, not
    guessed coordinates — so nothing drifts."""
    def __init__(self, width=None, height=180):
        super().__init__()
        self.width = width or 0
        self.height = height

    def wrap(self, avail_w, avail_h):
        self.width = avail_w
        return (avail_w, self.height)

    def drawOn(self, canv, x, y, _sW=0):
        # y is the bottom-left of this flowable on the canvas
        col_w = self.width / 3
        h = self.height

        names = ["Stefan Krüger", "Dr. Helga Mayer", "Klaus Weidmann"]
        title_lines = [
            ("Plant Director", "ACME Munich"),
            ("Chair, Works Council", "(Betriebsrat)"),
            ("Regional Secretary", "IG Metall Bayern"),
        ]
        dates = ["Signed: 18 Dec 2025", "Signed: 18 Dec 2025", "Signed: 19 Dec 2025"]
        stamp_initials = ["SK", "HM", "KW"]
        stamp_dates = ["18-12-2025", "18-12-2025", "19-12-2025"]

        # Top of block = y + h. Within block, we lay out top-down:
        #  - squiggle at y_squiggle
        #  - signature line at y_line
        #  - name at y_name
        #  - two title rows
        #  - date row
        #  - stamp below date, offset right

        y_line = y + h - 40      # signature line
        y_squiggle_base = y_line + 4   # squiggle rests just above the line
        y_name = y_line - 14     # name below line
        y_title1 = y_name - 14
        y_title2 = y_title1 - 12
        y_date = y_title2 - 20

        for i in range(3):
            col_x = x + col_w * i
            col_center = col_x + col_w / 2

            # Signature line
            canv.saveState()
            canv.setStrokeColor(RULE_GRAY)
            canv.setLineWidth(0.5)
            line_margin = col_w * 0.08
            canv.line(col_x + line_margin, y_line, col_x + col_w - line_margin, y_line)
            canv.restoreState()

            # Squiggle signature — positioned so it rests above the line
            sig_start_x = col_x + col_w * 0.18
            _draw_signature(canv, sig_start_x, y_squiggle_base, seed=i + 1)

            # Name
            canv.saveState()
            canv.setFillColor(colors.black)
            canv.setFont("Helvetica-Bold", 10)
            canv.drawCentredString(col_center, y_name, names[i])
            # Title lines
            canv.setFillColor(SOFT_GRAY)
            canv.setFont("Helvetica", 8.5)
            canv.drawCentredString(col_center, y_title1, title_lines[i][0])
            canv.drawCentredString(col_center, y_title2, title_lines[i][1])
            # Date
            canv.drawCentredString(col_center, y_date, dates[i])
            canv.restoreState()

            # Stamp — placed below date row, slightly offset to the right of center
            stamp_cx = col_center + col_w * 0.18
            stamp_cy = y_date - 40
            _draw_signed_stamp(canv, stamp_cx, stamp_cy, stamp_dates[i], stamp_initials[i])


class DocumentBarcode(Flowable):
    """Inline Flowable that draws the 'DOCUMENT CONTROL' label + barcode +
    reference number, self-contained so nothing overlaps with other flow."""
    def __init__(self, width=None, barcode_width=180, bar_height=32):
        super().__init__()
        self.width = width or 0
        self.barcode_width = barcode_width
        self.bar_height = bar_height
        self.height = 14 + bar_height + 14  # label + bars + ref text

    def wrap(self, avail_w, avail_h):
        self.width = avail_w
        return (avail_w, self.height)

    def drawOn(self, canv, x, y, _sW=0):
        center_x = x + self.width / 2
        # "DOCUMENT CONTROL" label
        canv.saveState()
        canv.setFillColor(SOFT_GRAY)
        canv.setFont("Helvetica-Bold", 7)
        label_y = y + self.height - 10
        canv.drawCentredString(center_x, label_y, "DOCUMENT CONTROL")
        canv.restoreState()

        # Barcode
        bars_x = center_x - self.barcode_width / 2
        bars_y = y + 14
        _draw_barcode(canv, bars_x, bars_y, width=self.barcode_width, height=self.bar_height)


def write_union_contract_pdf():
    path = OUT / "union_contract_munich.pdf"

    # Use BaseDocTemplate to get different templates for cover/body.
    doc = BaseDocTemplate(
        str(path),
        pagesize=A4,
        title="ACME Munich — IG Metall Collective Bargaining Agreement",
        author="ACME Logistics GmbH + IG Metall Bayern",
        subject="Collective Bargaining Agreement 2026-2027",
        creator="ACME Logistics GmbH — HR / Legal",
        leftMargin=2.2 * cm,
        rightMargin=2.2 * cm,
        topMargin=2.2 * cm,
        bottomMargin=2.2 * cm,
    )

    cover_frame = Frame(
        0, 0, A4[0], A4[1],
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        id="cover_frame",
    )
    body_frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        A4[0] - doc.leftMargin - doc.rightMargin,
        A4[1] - doc.topMargin - doc.bottomMargin,
        id="body_frame",
    )

    cover_template = PageTemplate(id="cover", frames=[cover_frame], onPage=_cover_page_content)
    body_template = PageTemplate(id="body", frames=[body_frame], onPage=_body_page_frame)
    doc.addPageTemplates([cover_template, body_template])

    # Paragraph styles
    base = ParagraphStyle(
        "base",
        parent=getSampleStyleSheet()["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        spaceAfter=6,
        textColor=colors.black,
    )
    section_head = ParagraphStyle(
        "section_head",
        parent=base,
        fontName="Helvetica-Bold",
        fontSize=12,
        textColor=ACME_BLUE_HEX,
        spaceBefore=14,
        spaceAfter=8,
    )
    small = ParagraphStyle(
        "small",
        parent=base,
        fontSize=8,
        leading=11,
        textColor=SOFT_GRAY,
    )
    pullquote = ParagraphStyle(
        "pullquote",
        parent=base,
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=15,
        textColor=ACME_BLUE_HEX,
        leftIndent=10,
        rightIndent=10,
        spaceBefore=6,
        spaceAfter=6,
    )

    def callout(text):
        """Pull-quote box — used to highlight §2, §5, §9."""
        p = Paragraph(text, pullquote)
        tbl = Table(
            [[p]],
            colWidths=[A4[0] - doc.leftMargin - doc.rightMargin - 10],
        )
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EAF1F9")),
            ("LEFTBORDERCOLOR", (0, 0), (0, 0), ACME_BLUE_HEX),
            ("LINEBEFORE", (0, 0), (0, 0), 3, ACME_BLUE_HEX),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ]))
        return tbl

    story = []

    # ----- Cover page (empty story frame — content painted in onPage) -----
    # Put NextPageTemplate BEFORE the PageBreak so page 2 uses body template.
    from reportlab.platypus import NextPageTemplate
    story.append(Spacer(1, A4[1] - 4))       # fills cover page
    story.append(NextPageTemplate("body"))   # schedule switch to body template
    story.append(PageBreak())                # end cover page

    # ----- Body pages — clauses verbatim from existing PDF -----
    story.append(Paragraph("ACME Logistics GmbH — Munich Distribution Center", ParagraphStyle(
        "h1", parent=base, fontName="Helvetica-Bold", fontSize=16,
        textColor=ACME_BLUE_HEX, spaceAfter=4,
    )))
    story.append(Paragraph("Collective Bargaining Agreement (IG Metall, Bayern)", ParagraphStyle(
        "h2", parent=base, fontName="Helvetica-Bold", fontSize=12,
        textColor=ACME_BLUE_HEX, spaceAfter=4,
    )))
    story.append(Paragraph("Effective: 01 January 2026 &nbsp;·&nbsp; Expires: 31 December 2027", small))
    story.append(HRFlowable(width="100%", thickness=0.4, color=RULE_GRAY, spaceBefore=6, spaceAfter=10))

    # §1 Scope
    story.append(Paragraph("§1 Scope", section_head))
    story.append(Paragraph(
        "This agreement covers all hourly warehouse, picking, packing, and forklift operators employed at "
        "the ACME Munich Distribution Center (Plant code DE-MUC-03). Salaried technical, administrative, "
        "and managerial personnel are excluded.",
        base))

    # §2 Regular Working Hours — with pull-quote
    story.append(Paragraph("§2 Regular Working Hours", section_head))
    story.append(Paragraph(
        "The regular shift shall not exceed <b>eight (8) hours</b> per working day, exclusive of the mandatory "
        "unpaid meal break. The weekly working time shall not exceed <b>forty-eight (48) hours</b> averaged over "
        "any rolling four (4) week period. Any planned shift exceeding 8h requires prior written consent from "
        "the Works Council (Betriebsrat).",
        base))
    story.append(callout(
        "§2 KEY CLAUSE — Regular shift: <b>max 8 hours per day.</b> "
        "Weekly cap: 48h rolling 4-week average. Overtime requires Works Council consent."
    ))

    # §3 Rest Breaks
    story.append(Paragraph("§3 Rest Breaks", section_head))
    story.append(Paragraph(
        "A paid rest break of <b>30 minutes</b> shall be granted for every shift of six (6) hours or longer. "
        "An additional 15-minute rest break is granted when the total shift length reaches 9 hours "
        "(subject to §4 overtime approval).",
        base))

    # §4 Overtime
    story.append(Paragraph("§4 Overtime", section_head))
    story.append(Paragraph(
        "Overtime is defined as any time worked in excess of the 8h regular shift defined in §2. Overtime "
        "must be approved in advance by the shift supervisor and reported within 24 hours to payroll.",
        base))
    story.append(Paragraph(
        "Weekday overtime up to two (2) hours per day is compensated at <b>125%</b> of base rate. Any additional "
        "hours beyond the first two are compensated at <b>150%</b>.",
        base))

    # §5 Weekend and Holiday Work — with pull-quote
    story.append(Paragraph("§5 Weekend and Holiday Work", section_head))
    story.append(Paragraph(
        "<b>Weekend overtime is prohibited</b> except in the case of a documented operational emergency "
        "(Notfall) declared in writing by a site director or above. Saturday work, when authorised, is "
        "compensated at 150%; Sunday and public-holiday work at 200%. No employee may be scheduled for more "
        "than two (2) consecutive weekends, and the subsequent weekend shall be a guaranteed rest period.",
        base))
    story.append(callout(
        "§5 KEY CLAUSE — <b>Weekend overtime is prohibited</b> except for documented Notfall "
        "(operational emergency) approved in writing by site director or above."
    ))

    story.append(PageBreak())

    # §6 Night Shift Premium
    story.append(Paragraph("§6 Night Shift Premium", section_head))
    story.append(Paragraph(
        "Hours worked between 22:00 and 06:00 attract a night-shift premium of 25% above base rate, in "
        "addition to any overtime premium under §4. Employees may not be scheduled for more than five (5) "
        "consecutive night shifts without an intervening 48-hour rest period.",
        base))

    # §7 Forklift and Heavy-Equipment Operators
    story.append(Paragraph("§7 Forklift and Heavy-Equipment Operators", section_head))
    story.append(Paragraph(
        "Certified forklift operators shall not operate heavy equipment for more than six (6) consecutive "
        "hours without a mandatory 20-minute rest. A minimum of one certified operator must be on site for "
        "every shift in which pallet movements exceed 50 units.",
        base))

    # §8 Seasonal Staffing and Temporary Labour
    story.append(Paragraph("§8 Seasonal Staffing and Temporary Labour", section_head))
    story.append(Paragraph(
        "Temporary agency labour may not exceed 15% of headcount on any given shift. During peak months "
        "(defined as April–June and October–December), this cap may be raised to 25% with Works Council "
        "approval, provided all temporary staff receive the same base rate as equivalent permanent staff.",
        base))

    # §9 Capacity Reporting — with pull-quote (critical for the demo's unit-mismatch trap)
    story.append(Paragraph("§9 Capacity Reporting", section_head))
    story.append(Paragraph(
        "For the purposes of operational reporting, warehouse throughput at the Munich DC shall be measured "
        "in <b>kilograms</b> to match the historical record system (SAP IM-WM module DE-MUC-03 pre-dates the "
        "2023 metric harmonisation and retains kg as its native unit). Reports submitted to central planning "
        "in Frankfurt are automatically converted to tonnes downstream.",
        base))
    story.append(callout(
        "§9 KEY CLAUSE — <b>Munich DC capacity is reported in kilograms.</b> "
        "Legacy SAP IM-WM DE-MUC-03 predates 2023 metric harmonisation. "
        "Downstream systems must convert to tonnes."
    ))

    # §10 Dispute Resolution
    story.append(Paragraph("§10 Dispute Resolution", section_head))
    story.append(Paragraph(
        "All disputes arising under this agreement shall first be addressed through the Works Council. "
        "Unresolved matters may be escalated to the IG Metall Bayern regional office within 30 calendar days.",
        base))

    # ----- Signature page -----
    story.append(PageBreak())
    story.append(Paragraph("Signatures", section_head))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "The undersigned parties have reviewed and approved the foregoing agreement. This agreement is "
        "executed in three (3) original counterparts in the German language, one for each signatory party.",
        base))
    story.append(Spacer(1, 24))

    # Three-column signature block — signature lines, squiggles, names,
    # titles, dates, and stamps, all drawn together at the layout-determined
    # Y position. No post-processing overlay.
    story.append(SignatureBlock(height=180))

    story.append(Spacer(1, 30))
    story.append(Paragraph(
        "Document control — scan the barcode below or quote reference <b>BV-MUC-2026-003</b>.",
        small))
    story.append(Spacer(1, 10))
    story.append(DocumentBarcode())

    # Build — single pass, no overlay needed.
    doc.build(story)
    print(f"  ✓ {path.name}  ({path.stat().st_size}B)")


# =========================================================================
# 5. instructions.txt  (Outlook email format)
# =========================================================================
def write_instructions():
    path = OUT / "instructions.txt"
    path.write_text(
        """From:       Stefan Krüger <s.krueger@acme-logistics.de>
To:         Planning Team <planning-ops@acme-logistics.de>
CC:         Works Council <br-muc@acme-logistics.de>; Isabelle Weber <i.weber@acme-logistics.de>
Sent:       Monday, 20 April 2026 08:14 CEST
Subject:    Q2 2026 Distribution Plan — Munich, Berlin, Hamburg  [REQ-2026-Q2-0417]
Priority:   High
Importance: High

Team,

Please run the Q2 2026 distribution optimization for our Germany DC network.
Attached: capacity CSV, routing matrix, demand forecast (Rev. 3), and the
Munich IG Metall collective agreement. We need the model submitted to
Quantagonia this morning so I can review with Isabelle before the Q2 kickoff
at 14:00.

Objective
---------
Minimize total routing cost in EUR across SKU-001 / SKU-002 / SKU-003
shipped from W1 (Hamburg), W2 (Berlin), W3 (Munich) to D1 (Paris),
D2 (Vienna), D3 (Amsterdam), over the April – June 2026 horizon.

Constraints
-----------
  - Monthly warehouse capacities per the attached capacity CSV.
    Note: Munich (W3) is reported in kilograms — see §9 of the IG Metall
    agreement. Planning, please confirm the normalisation before submit.
  - Monthly SKU demand per the attached XLSX (tabs Apr / May / Jun;
    Summary is informational).
  - Munich labour rules per §1–§10 of the IG Metall agreement. In particular:
      * §2: 8h shift cap, 48h rolling 4-week weekly cap.
      * §5: Weekend overtime PROHIBITED (no exceptions this quarter —
            we have no declared Notfall).
      * §9: Capacity at Munich DC reported in kg, must convert to tonnes
            before entering the solver.
  - Prefer Munich (W3) for SKU-001 where routing cost is competitive —
    this aligns with the board's decision to rebalance southern European
    demand through Munich this quarter.
  - All demand must be fully satisfied (no backorders).

Deliverable
-----------
Optimal shipment plan by warehouse × destination × SKU × month, plus
total cost (EUR) and per-warehouse utilisation (% of monthly capacity).
Please push the solution summary back into this thread; I want Kleinert's
team to see the cold start timing against their HybridSolver bench.

No need to copy me on the intermediate extraction previews — the agent's
Slack posts are fine. Flag only if the validator trips or the solver
returns anything over 1% gap.

Thanks,
Stefan

---
Stefan Krüger
Plant Director — ACME Munich Distribution Center
ACME Logistics GmbH
Hansastraße 42, 80686 München, Deutschland
T: +49 (0) 89 4441 2030   M: +49 (0) 171 225 8842
s.krueger@acme-logistics.de

---
Diese E-Mail und ihre Anhänge können vertrauliche und/oder rechtlich
geschützte Informationen enthalten. Wenn Sie nicht der richtige Adressat
sind, informieren Sie bitte sofort den Absender und vernichten Sie diese
E-Mail. Das unerlaubte Kopieren sowie die unbefugte Weitergabe dieser
E-Mail sind nicht gestattet.

This e-mail and any attachments may contain confidential and/or privileged
information. If you are not the intended recipient, please notify the
sender immediately and delete this e-mail. Unauthorised copying and
distribution of this e-mail are prohibited.

ACME Logistics GmbH · Sitz München · Handelsregister: HRB 142 889 München
Geschäftsführung: S. Krüger, I. Weber · USt-IdNr.: DE 247 881 330
""",
        encoding="utf-8",
    )
    print(f"  ✓ {path.name}  ({path.stat().st_size}B)")


# =========================================================================
# 6. cover_sheet.pdf  (bonus — routing cover sheet)
# =========================================================================
def write_cover_sheet_pdf():
    path = OUT / "cover_sheet.pdf"

    # Page 1: header letterhead + footer. No big stamp here (it overlaps
    # the opaque fields table).
    def on_page_1(canv, doc):
        # Paper tint
        canv.saveState()
        canv.setFillColor(PAPER)
        canv.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        canv.restoreState()

        # Letterhead
        _draw_acme_logo(canv, 2.2 * cm, A4[1] - 2.6 * cm, scale=1.3)
        canv.setFont("Helvetica", 8)
        canv.setFillColor(SOFT_GRAY)
        canv.drawRightString(
            A4[0] - 2.2 * cm,
            A4[1] - 2.0 * cm,
            "Hansastraße 42, 80686 München  ·  +49 (0) 89 4441 2030",
        )
        canv.drawRightString(
            A4[0] - 2.2 * cm,
            A4[1] - 2.4 * cm,
            "planning-ops@acme-logistics.de  ·  HRB 142 889 München",
        )

        # Rule
        canv.setStrokeColor(ACME_BLUE_HEX)
        canv.setLineWidth(1.2)
        canv.line(2.2 * cm, A4[1] - 3.0 * cm, A4[0] - 2.2 * cm, A4[1] - 3.0 * cm)

        # Footer
        canv.setFont("Helvetica", 7.5)
        canv.setFillColor(SOFT_GRAY)
        canv.drawCentredString(
            A4[0] / 2,
            1.4 * cm,
            "Document ID: REQ-2026-Q2-0417    •    Revision 1    •    Generated 2026-04-20 08:12 CEST",
        )

    # Page 2: same letterhead + footer, PLUS a big red "APPROVED FOR SOLVER"
    # stamp placed over the Approvals area. This runs BEFORE flowables so
    # flowables would normally cover it — we draw it in an afterFlowable pass
    # via a custom DocTemplate callback instead.
    class _StampedDocTemplate(SimpleDocTemplate):
        def afterFlowable(self, flowable):
            pass

        def handle_pageEnd(self):
            # Draw stamp on page 2 after all flowables (so it sits on top).
            if self.page == 2:
                c = self.canv
                c.saveState()
                stamp_x = A4[0] - 5.0 * cm
                stamp_y = 8.0 * cm
                c.translate(stamp_x, stamp_y)
                c.rotate(-12)
                c.setStrokeColor(ACME_RED)
                c.setFillColor(ACME_RED)
                c.setLineWidth(2.2)
                c.roundRect(-85, -34, 170, 68, 8, stroke=1, fill=0)
                c.roundRect(-80, -29, 160, 58, 6, stroke=1, fill=0)
                c.setFont("Helvetica-Bold", 15)
                c.drawCentredString(0, 10, "APPROVED")
                c.drawCentredString(0, -7, "FOR SOLVER")
                c.setFont("Helvetica", 7)
                c.drawCentredString(0, -22, "S.K.  ·  2026-04-20")
                c.restoreState()
            super().handle_pageEnd()

    doc = _StampedDocTemplate(
        str(path), pagesize=A4,
        leftMargin=2.2 * cm, rightMargin=2.2 * cm,
        topMargin=3.4 * cm, bottomMargin=2.2 * cm,
        title="Planning Request Intake Form — REQ-2026-Q2-0417",
        author="ACME Logistics GmbH",
        subject="Q2 2026 distribution planning request",
        creator="ACME S&amp;OP Planning",
    )
    styles = getSampleStyleSheet()
    base = ParagraphStyle(
        "base", parent=styles["BodyText"], fontName="Helvetica", fontSize=10,
        leading=14, spaceAfter=4, textColor=colors.black,
    )
    title = ParagraphStyle(
        "title", parent=base, fontName="Helvetica-Bold", fontSize=18,
        textColor=ACME_BLUE_HEX, spaceAfter=4, alignment=TA_LEFT,
    )
    subtitle = ParagraphStyle(
        "subtitle", parent=base, fontName="Helvetica", fontSize=10,
        textColor=SOFT_GRAY, spaceAfter=12,
    )
    section = ParagraphStyle(
        "section", parent=base, fontName="Helvetica-Bold", fontSize=11,
        textColor=ACME_BLUE_HEX, spaceBefore=10, spaceAfter=6,
    )

    story = []

    story.append(Paragraph("Planning Request Intake Form", title))
    # Escape ampersand for HTML mini-markup in Paragraph
    story.append(Paragraph("S&amp;OP Planning — Germany DC Network", subtitle))
    story.append(HRFlowable(width="100%", thickness=0.4, color=RULE_GRAY, spaceAfter=10))

    # Fields as a tidy two-column table. Use "≤" encoded via Paragraph with
    # HTML entity so it renders correctly in Helvetica fallback.
    fields = [
        ("Request ID", "REQ-2026-Q2-0417"),
        ("Submitted by", "Stefan Krüger  —  Plant Director, ACME Munich"),
        ("Date submitted", "Monday, 20 April 2026  ·  08:14 CEST"),
        ("Planning horizon", "Q2 2026  (01 Apr – 30 Jun 2026)"),
        ("Scope", "Germany DC network: W1 Hamburg, W2 Berlin, W3 Munich"),
        ("Destinations", "D1 Paris  ·  D2 Vienna  ·  D3 Amsterdam"),
        ("SKUs in scope", "SKU-001, SKU-002, SKU-003"),
        ("Priority", "High"),
        ("Target solver", "Quantagonia HybridSolver  (MILP / LP)"),
        ("Expected turnaround", "&lt; 4 hours end-to-end"),
        ("Budget", "Max 8 solver-minutes this request (tenant: acme-logistics)"),
        ("Classification", "Confidential — Internal Use Only"),
    ]
    rows = []
    for k, v in fields:
        rows.append([
            Paragraph(f"<b>{k}</b>", base),
            Paragraph(v, base),
        ])
    field_tbl = Table(rows, colWidths=[4.6 * cm, None])
    field_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TEXTCOLOR", (0, 0), (0, -1), ACME_BLUE_HEX),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FAF6EC")),
        ("BOX", (0, 0), (-1, -1), 0.4, RULE_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E6E0D2")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(field_tbl)

    # Attachments checklist
    story.append(Paragraph("Attachments Checklist", section))
    attachments = [
        ("warehouse_capacity.csv", "Warehouse monthly capacities (Hamburg, Berlin, Munich)."),
        ("routing_matrix.csv", "Cost EUR/ton across 27 warehouse × destination × SKU combinations."),
        ("demand_forecast_q2.xlsx", "Monthly demand by SKU and destination, plus Q2 summary (Rev. 3)."),
        ("union_contract_munich.pdf", "IG Metall collective agreement (BV-MUC-2026-003) — §2, §5, §9 relevant."),
    ]
    rows = [[Paragraph("<b>\u2611</b>", ParagraphStyle(
        "tick", parent=base, fontName="Helvetica-Bold", fontSize=13,
        textColor=ACME_BLUE_HEX,
    )), Paragraph(f"<b>{name}</b>", base), Paragraph(desc, base)] for name, desc in attachments]
    att_tbl = Table(rows, colWidths=[0.9 * cm, 5.2 * cm, None])
    att_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#E6E0D2")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FDFCF7")),
    ]))
    story.append(att_tbl)

    # Notes
    story.append(Paragraph("Planning Notes", section))
    notes = [
        "All monthly demand must be fully satisfied — no backorders permitted this quarter.",
        "Munich DC (W3) capacity is reported in <b>kilograms</b> per §9 of the collective agreement. "
        "The solver intake agent is responsible for normalising to tonnes before compilation.",
        "SKU-001 should prefer Munich (W3) routing where cost-effective, consistent with the Q1 board "
        "decision on southern European demand.",
        "Weekend overtime is <b>not permitted</b> this quarter (§5). No Notfall declared.",
    ]
    for n in notes:
        story.append(Paragraph(f"• {n}", base))
        story.append(Spacer(1, 2))

    # Approvals block — pushed to page 2 so the stamp sits on a clean canvas
    story.append(PageBreak())
    story.append(Paragraph("Approvals", section))
    approvals = [
        ["Submitted by:", "Stefan Krüger", "20-04-2026 08:14"],
        ["Reviewed by:", "Isabelle Weber (CFO)", "20-04-2026 08:31"],
        ["Authorised for solver:", "S. Krüger  (see stamp)", "20-04-2026 08:45"],
    ]
    app_tbl = Table(approvals, colWidths=[5.2 * cm, 6.2 * cm, 3.8 * cm])
    app_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), ACME_BLUE_HEX),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#E6E0D2")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(app_tbl)
    story.append(Spacer(1, 18))
    story.append(Paragraph(
        "The stamp below authorises this request for direct submission to the Quantagonia HybridSolver via the "
        "ACME S&amp;OP intake pipeline. Retain this cover sheet with the run artifacts for audit.",
        ParagraphStyle("note", parent=base, fontSize=9, textColor=SOFT_GRAY, leading=12),
    ))

    doc.build(story, onFirstPage=on_page_1, onLaterPages=on_page_1)
    print(f"  ✓ {path.name}  ({path.stat().st_size}B)")


# =========================================================================
# MAIN
# =========================================================================
def main():
    print(f"Building polished ACME Q2 2026 fixtures in: {OUT}")
    print()
    write_capacity()
    write_routing()
    write_demand_xlsx()
    write_union_contract_pdf()
    write_instructions()
    write_cover_sheet_pdf()
    print()
    print("Done.")


if __name__ == "__main__":
    main()
