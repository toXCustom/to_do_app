"""
export.py — Export tasks to CSV, PDF, or TXT
=============================================
All three functions accept a list of Task objects and a file path string.
PDF requires reportlab (pip install reportlab).
"""
import csv
from datetime import date


# ── CSV ────────────────────────────────────────────────────────────────────────

def export_csv(tasks: list, path: str) -> None:
    """Write tasks to a UTF-8 CSV file with a header row."""
    fields = ["Name", "Description", "Category", "Priority",
              "Due Date", "Done", "Overdue"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for t in tasks:
            writer.writerow({
                "Name":        t.name,
                "Description": t.description,
                "Category":    getattr(t, "category", "General"),
                "Priority":    t.priority,
                "Due Date":    t.due_date.strftime("%Y-%m-%d") if t.due_date else "",
                "Done":        "Yes" if t.done else "No",
                "Overdue":     "Yes" if getattr(t, "is_overdue", False) else "No",
            })


# ── TXT ────────────────────────────────────────────────────────────────────────

def export_txt(tasks: list, path: str) -> None:
    """Write tasks as a readable plain-text report."""
    today = date.today().strftime("%d %B %Y")
    lines = [
        "MY TASKS",
        f"Exported: {today}",
        f"Total: {len(tasks)}  |  Done: {sum(1 for t in tasks if t.done)}"
        f"  |  Active: {sum(1 for t in tasks if not t.done)}",
        "=" * 60,
        "",
    ]

    # Group by category
    from collections import defaultdict
    grouped = defaultdict(list)
    for t in tasks:
        grouped[getattr(t, "category", "General")].append(t)

    for cat, cat_tasks in sorted(grouped.items()):
        lines.append(f"[ {cat.upper()} ]")
        lines.append("-" * 40)
        for t in cat_tasks:
            status  = "✓" if t.done else "○"
            overdue = " ⚠ OVERDUE" if getattr(t, "is_overdue", False) and not t.done else ""
            due_str = f"  Due: {t.due_date.strftime('%Y-%m-%d')}" if t.due_date else ""
            pri_map = {"High": "🔥", "Medium": "⚡", "Low": "🌿"}
            icon    = pri_map.get(t.priority, "•")
            lines.append(f"  {status} {icon} {t.name}{due_str}{overdue}")
            if t.description:
                lines.append(f"      {t.description}")
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ── PDF ────────────────────────────────────────────────────────────────────────

def export_pdf(tasks: list, path: str) -> None:
    """Write tasks to a styled PDF report using reportlab."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        )
        from reportlab.lib.enums import TA_LEFT, TA_CENTER
    except ImportError:
        raise ImportError("reportlab is required for PDF export.\n"
                          "Install it with:  pip install reportlab")

    today  = date.today().strftime("%d %B %Y")
    WIDTH, HEIGHT = A4

    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm,  bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    accent = colors.HexColor("#C2622D")

    TITLE   = ParagraphStyle("Title2",   fontSize=22, leading=26,
                              textColor=accent,        spaceAfter=4)
    SUBTITLE= ParagraphStyle("Sub",      fontSize=10, leading=14,
                              textColor=colors.HexColor("#78716C"), spaceAfter=14)
    CAT_HDR = ParagraphStyle("CatHdr",   fontSize=12, leading=16,
                              textColor=accent,        fontName="Helvetica-Bold",
                              spaceBefore=14, spaceAfter=4)
    NORMAL  = ParagraphStyle("Norm",     fontSize=9,  leading=13,
                              textColor=colors.HexColor("#1C1917"))
    MUTED   = ParagraphStyle("Muted",    fontSize=8,  leading=11,
                              textColor=colors.HexColor("#78716C"),
                              leftIndent=12)

    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(Paragraph("My Tasks", TITLE))
    done_count   = sum(1 for t in tasks if t.done)
    active_count = len(tasks) - done_count
    overdue_cnt  = sum(1 for t in tasks if getattr(t, "is_overdue", False) and not t.done)
    story.append(Paragraph(
        f"Exported {today}  &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"{len(tasks)} tasks &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"{active_count} active &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"{done_count} done &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"{overdue_cnt} overdue",
        SUBTITLE
    ))
    story.append(HRFlowable(width="100%", thickness=1,
                             color=colors.HexColor("#E0D9CF"), spaceAfter=6))

    # ── Table ─────────────────────────────────────────────────────────────────
    header_row = ["", "Task Name", "Category", "Priority", "Due Date", "Status"]
    rows = [header_row]

    pri_label = {"High": "High", "Medium": "Medium", "Low": "Low"}
    for t in tasks:
        status  = "Done"    if t.done else ("Overdue" if getattr(t, "is_overdue", False) else "Active")
        due_str = t.due_date.strftime("%d %b %Y") if t.due_date else "—"
        bullet  = "✓" if t.done else "○"
        rows.append([
            bullet,
            t.name,
            getattr(t, "category", "General"),
            pri_label.get(t.priority, t.priority),
            due_str,
            status,
        ])

    col_widths = [0.6*cm, 6.5*cm, 3*cm, 2.2*cm, 2.8*cm, 2.2*cm]
    tbl = Table(rows, colWidths=col_widths, repeatRows=1)

    tbl_style = TableStyle([
        # Header
        ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#F2EDE6")),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.HexColor("#78716C")),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING",(0, 0), (-1, 0), 6),
        ("TOPPADDING",  (0, 0), (-1, 0), 6),
        # Body
        ("FONTNAME",    (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",    (0, 1), (-1, -1), 8.5),
        ("TOPPADDING",  (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 1), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
            [colors.white, colors.HexColor("#FAF7F2")]),
        # Grid
        ("LINEBELOW",   (0, 0), (-1, 0), 1, colors.HexColor("#E0D9CF")),
        ("LINEBELOW",   (0, 1), (-1, -1), 0.3, colors.HexColor("#E0D9CF")),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
    ])

    # Colour status column
    for i, t in enumerate(tasks, start=1):
        if t.done:
            tbl_style.add("TEXTCOLOR", (5, i), (5, i), colors.HexColor("#065F46"))
        elif getattr(t, "is_overdue", False):
            tbl_style.add("TEXTCOLOR", (5, i), (5, i), colors.HexColor("#991B1B"))
            tbl_style.add("FONTNAME",  (5, i), (5, i), "Helvetica-Bold")
        # Strike-through done tasks in name col via grey text
        if t.done:
            tbl_style.add("TEXTCOLOR", (1, i), (1, i), colors.HexColor("#A8A29E"))

    tbl.setStyle(tbl_style)
    story.append(tbl)
    story.append(Spacer(1, 0.4*cm))

    # ── Footer note ───────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=colors.HexColor("#E0D9CF"), spaceBefore=6))
    story.append(Paragraph(
        f"Generated by My Tasks app &nbsp;|&nbsp; {today}",
        MUTED
    ))

    doc.build(story)