import csv
import io

CSV_COLUMNS = [
    ("id", "Incident ID"),
    ("detected_at", "Detected at"),
    ("camera_name", "Camera"),
    ("object_class", "Object"),
    ("object_track_id", "Object track ID"),
    ("person_track_id", "Person track ID"),
    ("distance", "Distance (px)"),
    ("distance_threshold", "Distance threshold (px)"),
    ("time_threshold", "Time threshold (s)"),
    ("status", "Status"),
    ("review_status", "Review"),
    ("review_note", "Review note"),
    ("reviewed_by", "Reviewed by"),
    ("reviewed_at", "Reviewed at"),
]

# Spreadsheets run a cell as a formula if it starts with one of these characters.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _cell(value):
    if value is None:
        return ""
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


AUDIT_COLUMNS = [
    ("id", "Entry ID"),
    ("created_at", "Recorded at"),
    ("actor", "User"),
    ("action", "Action"),
    ("detail", "Detail"),
    ("entry_hash", "Entry hash"),
]


def audit_to_csv(entries) -> bytes:
    """The audit trail as CSV, with the same formula protection and encoding as the incident export."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow([label for _, label in AUDIT_COLUMNS])
    for entry in entries:
        writer.writerow([_cell(entry.get(key)) for key, _ in AUDIT_COLUMNS])
    return b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")


def incidents_to_csv(incidents) -> bytes:
    """
    Serialises incidents as CSV. UTF-8 with a byte-order mark so Excel reads accents correctly.
    The timeline and snapshot are left out; the CSV holds one row per incident.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow([label for _, label in CSV_COLUMNS])
    for incident in incidents:
        writer.writerow([_cell(incident.get(key)) for key, _ in CSV_COLUMNS])
    return b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")
