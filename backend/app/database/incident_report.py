import io
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

MUTED = colors.HexColor("#6b7280")
RULE = colors.HexColor("#d1d5db")


def _display_time(iso_value):
    if not iso_value:
        return "-"
    try:
        return datetime.fromisoformat(iso_value).strftime("%d %b %Y, %H:%M:%S")
    except ValueError:
        return str(iso_value)


def _value(value, suffix=""):
    if value is None or value == "":
        return "-"
    return f"{value}{suffix}"


def _grid(rows, col_widths):
    table = Table(rows, colWidths=col_widths, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def incident_to_pdf(incident, snapshot_bytes, generated_by, generated_at=None) -> bytes:
    """
    One-page report for a single incident: the snapshot, object and review details,
    the state timeline, and the thresholds the detector used.
    """
    generated_at = generated_at or datetime.now()
    styles = getSampleStyleSheet()
    title = styles["Title"]
    heading = styles["Heading3"]
    body = styles["BodyText"]
    small = ParagraphStyle("small", parent=body, fontSize=8, textColor=MUTED)

    story = [
        Paragraph(f"Incident #{incident['id']}", title),
        Paragraph(
            f"{escape(_display_time(incident['detected_at']))} &middot; {escape(_value(incident.get('camera_name')))}",
            body,
        ),
        Spacer(1, 6 * mm),
    ]

    if snapshot_bytes:
        reader = ImageReader(io.BytesIO(snapshot_bytes))
        width_px, height_px = reader.getSize()
        width = 150 * mm
        height = min(width * height_px / width_px, 110 * mm)
        story += [Image(io.BytesIO(snapshot_bytes), width=width, height=height, hAlign="LEFT"), Spacer(1, 6 * mm)]
    else:
        story += [Paragraph("No snapshot was saved for this incident.", small), Spacer(1, 6 * mm)]

    col = [42 * mm, 130 * mm]
    story += [
        Paragraph("Object and detection", heading),
        _grid([
            ["Object", escape(_value(incident["object_class"]))],
            ["Object track ID", _value(incident.get("object_track_id"))],
            ["Person track ID", _value(incident.get("person_track_id"))],
            ["Distance at alert", _value(round(incident["distance"]) if incident.get("distance") is not None else None, " px")],
            ["Status", escape(_value(incident.get("status")))],
        ], col),
        Spacer(1, 5 * mm),
        Paragraph("Settings used", heading),
        _grid([
            ["Distance threshold", _value(incident.get("distance_threshold"), " px")],
            ["Time threshold", _value(incident.get("time_threshold"), " s")],
            ["Camera", escape(_value(incident.get("camera_name")))],
        ], col),
        Spacer(1, 5 * mm),
        Paragraph("Review", heading),
        _grid([
            ["Review", escape(_value(incident.get("review_status")))],
            ["Note", escape(_value(incident.get("review_note")))],
            ["Reviewed by", escape(_value(incident.get("reviewed_by")))],
            ["Reviewed at", escape(_display_time(incident.get("reviewed_at")) if incident.get("reviewed_at") else "-")],
        ], col),
        Spacer(1, 5 * mm),
        Paragraph("Timeline", heading),
    ]

    history = incident.get("state_history") or []
    if history:
        timeline = [["Time", "State"]] + [
            [_display_time(entry.get("time")), escape(str(entry.get("state", "")))] for entry in history
        ]
        story.append(_grid(timeline, [60 * mm, 112 * mm]))
    else:
        story.append(Paragraph("No state history was recorded.", small))

    story += [
        Spacer(1, 8 * mm),
        Paragraph(
            f"Generated {generated_at.strftime('%d %b %Y, %H:%M:%S')} by {escape(generated_by)} from the VigiTrack hub.",
            small,
        ),
    ]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"VigiTrack incident #{incident['id']}",
        author="VigiTrack",
    )
    doc.build(story)
    return buffer.getvalue()
