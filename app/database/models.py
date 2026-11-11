from datetime import datetime
from app.database.db import get_connection


def log_incident(object_class, object_track_id, person_track_id, distance, camera_name="CAMERA 01"):
    """
    Inserts a new unattended-object incident record.
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
                detected_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            str(object_class),
            int(object_track_id) if object_track_id is not None else None,
            int(person_track_id) if person_track_id is not None else None,
            dist_val,
            str(camera_name),
            "unattended",
            now_str
        ))
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        print(f"[Database Error] Failed to log incident for object ID {object_track_id}: {e}")
        return None
    finally:
        conn.close()


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
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"[Database Error] Failed to retrieve incidents: {e}")
        return []
    finally:
        conn.close()


def delete_incident(incident_id: int) -> bool:
    """Deletes a single incident record by ID."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM incidents WHERE id = ?", (incident_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"[Database Error] Failed to delete incident {incident_id}: {e}")
        return False
    finally:
        conn.close()


def clear_all_incidents() -> int:
    """Clears all incident records from the database."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM incidents")
        count = cursor.rowcount
        conn.commit()
        return count
    except Exception as e:
        print(f"[Database Error] Failed to clear incidents: {e}")
        return 0
    finally:
        conn.close()
