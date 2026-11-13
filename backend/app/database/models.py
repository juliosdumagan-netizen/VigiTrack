import json
import os
from datetime import datetime
from app.database.db import DB_PATH, get_connection

INCIDENT_IMAGE_DIR = os.path.join(os.path.dirname(DB_PATH), "incidents")


def _row_to_incident(row):
    item = dict(row)
    raw_history = item.pop("state_history", None)
    item["state_history"] = json.loads(raw_history) if raw_history else []
    image_path = item.pop("image_path", None)
    item["image_url"] = f"/api/incidents/{item['id']}/image" if image_path else None
    return item


def _remove_image_file(filename):
    if not filename:
        return
    path = os.path.join(INCIDENT_IMAGE_DIR, os.path.basename(filename))
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except OSError as e:
        print(f"[Database Error] Could not remove snapshot {path}: {e}")


def log_incident(object_class, object_track_id, person_track_id, distance, camera_name="CAMERA 01",
                 image_bytes=None, state_history=None, distance_threshold=None, time_threshold=None):
    """
    Inserts a new unattended-object incident record, with an optional JPEG snapshot.
    Returns the new incident's row id, or None if logging failed.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        now_str = datetime.now().isoformat(timespec="seconds")
        dist_val = round(float(distance), 2) if distance is not None else None

        cursor.execute("""
            INSERT INTO incidents (
                object_class,
                object_track_id,
                person_track_id,
                distance,
                camera_name,
                status,
                detected_at,
                state_history,
                distance_threshold,
                time_threshold
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(object_class),
            int(object_track_id) if object_track_id is not None else None,
            int(person_track_id) if person_track_id is not None else None,
            dist_val,
            str(camera_name),
            "unattended",
            now_str,
            json.dumps(state_history or []),
            float(distance_threshold) if distance_threshold is not None else None,
            float(time_threshold) if time_threshold is not None else None,
        ))
        incident_id = cursor.lastrowid

        if image_bytes:
            os.makedirs(INCIDENT_IMAGE_DIR, exist_ok=True)
            filename = f"{incident_id}.jpg"
            with open(os.path.join(INCIDENT_IMAGE_DIR, filename), "wb") as f:
                f.write(image_bytes)
            cursor.execute("UPDATE incidents SET image_path = ? WHERE id = ?", (filename, incident_id))

        conn.commit()
        return incident_id
    except Exception as e:
        print(f"[Database Error] Failed to log incident for object ID {object_track_id}: {e}")
        return None
    finally:
        conn.close()


REVIEW_ACTIONS = ("acknowledged", "verified", "dismissed")
REVIEW_NOTE_MAX = 500


def review_incident(incident_id: int, action: str, actor: str, note=None):
    """
    Records an operator's review of an incident.
    Returns (incident, None) on success, or (None, error message) on failure.
    'dismissed' (false alarm) must include a reason, so the false-alarm record is useful later.
    """
    if action not in REVIEW_ACTIONS:
        return None, "Action must be acknowledged, verified or dismissed."
    note = (str(note).strip() if note is not None else "") or None
    if note and len(note) > REVIEW_NOTE_MAX:
        return None, f"Note must be {REVIEW_NOTE_MAX} characters or fewer."
    if action == "dismissed" and not note:
        return None, "Give a reason when dismissing an alert as a false alarm."

    conn = get_connection()
    try:
        exists = conn.execute("SELECT 1 FROM incidents WHERE id = ?", (incident_id,)).fetchone()
        if exists is None:
            return None, "Incident not found."
        conn.execute(
            "UPDATE incidents SET review_status = ?, review_note = ?, reviewed_by = ?, reviewed_at = ? WHERE id = ?",
            (action, note, actor, datetime.now().isoformat(timespec="seconds"), incident_id),
        )
        conn.commit()
    finally:
        conn.close()
    return get_incident(incident_id), None


def get_all_incidents(limit=100):
    """
    Returns the most recent incidents, newest first.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM incidents
            ORDER BY detected_at DESC, id DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        return [_row_to_incident(row) for row in rows]
    except Exception as e:
        print(f"[Database Error] Failed to retrieve incidents: {e}")
        return []
    finally:
        conn.close()


def get_incident(incident_id: int):
    """Returns one incident with its state history, or None if it does not exist."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        row = cursor.fetchone()
        return _row_to_incident(row) if row else None
    except Exception as e:
        print(f"[Database Error] Failed to retrieve incident {incident_id}: {e}")
        return None
    finally:
        conn.close()


def get_incident_image_filename(incident_id: int):
    """Returns the stored snapshot filename for an incident, or None."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT image_path FROM incidents WHERE id = ?", (incident_id,))
        row = cursor.fetchone()
        return row["image_path"] if row and row["image_path"] else None
    except Exception as e:
        print(f"[Database Error] Failed to read image for incident {incident_id}: {e}")
        return None
    finally:
        conn.close()


def delete_incident(incident_id: int) -> bool:
    """Deletes a single incident record and its snapshot by ID."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT image_path FROM incidents WHERE id = ?", (incident_id,))
        row = cursor.fetchone()
        cursor.execute("DELETE FROM incidents WHERE id = ?", (incident_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        if deleted and row:
            _remove_image_file(row["image_path"])
        return deleted
    except Exception as e:
        print(f"[Database Error] Failed to delete incident {incident_id}: {e}")
        return False
    finally:
        conn.close()


def clear_all_incidents() -> int:
    """Clears all incident records and their snapshots from the database."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT image_path FROM incidents WHERE image_path IS NOT NULL")
        image_files = [row["image_path"] for row in cursor.fetchall()]
        cursor.execute("DELETE FROM incidents")
        count = cursor.rowcount
        conn.commit()
        for filename in image_files:
            _remove_image_file(filename)
        return count
    except Exception as e:
        print(f"[Database Error] Failed to clear incidents: {e}")
        return 0
    finally:
        conn.close()
