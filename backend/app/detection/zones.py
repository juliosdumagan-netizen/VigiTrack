"""
Ignore and watch zones, drawn on the camera view.

Zones are stored as polygons in normalised coordinates (0 to 1 across the frame),
so they stay correct if the camera resolution changes. They are converted to pixels
once the frame size is known.

- ignore: an object whose centre is inside is never tracked, so it cannot raise an alert.
- watch: an unattended object whose centre is inside uses the zone's own time limit
  (seconds) instead of the global one. If zones overlap, the shortest limit applies.
"""

from typing import Dict, List, Optional, Sequence, Tuple

ZONE_KINDS = ("ignore", "watch")
MAX_ZONES = 20
MAX_POINTS = 50
MAX_NAME_LENGTH = 40
MAX_WATCH_SECONDS = 3600.0

Point = Tuple[float, float]


class ZoneError(ValueError):
    """Raised when a zone definition is not valid."""


def _polygon_contains(point: Point, polygon: Sequence[Point]) -> bool:
    """Ray-casting point-in-polygon test."""
    x, y = point
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def normalise_zones(raw) -> List[Dict]:
    """
    Validates zones sent by the hub and returns clean copies.
    Raises ZoneError with a message the operator can act on.
    """
    if not isinstance(raw, list):
        raise ZoneError("Zones must be a list.")
    if len(raw) > MAX_ZONES:
        raise ZoneError(f"Use at most {MAX_ZONES} zones.")

    cleaned = []
    for index, zone in enumerate(raw, start=1):
        if not isinstance(zone, dict):
            raise ZoneError(f"Zone {index} is not valid.")

        kind = str(zone.get("type") or "")
        if kind not in ZONE_KINDS:
            raise ZoneError(f"Zone {index}: type must be ignore or watch.")

        name = str(zone.get("name") or "").strip() or f"Zone {index}"
        if len(name) > MAX_NAME_LENGTH:
            raise ZoneError(f"Zone {index}: the name must be {MAX_NAME_LENGTH} characters or fewer.")

        points_raw = zone.get("points")
        if not isinstance(points_raw, list) or len(points_raw) < 3:
            raise ZoneError(f"Zone '{name}' needs at least three points.")
        if len(points_raw) > MAX_POINTS:
            raise ZoneError(f"Zone '{name}' can have at most {MAX_POINTS} points.")

        points = []
        for p in points_raw:
            try:
                x, y = float(p[0]), float(p[1])
            except (TypeError, ValueError, IndexError):
                raise ZoneError(f"Zone '{name}' has a point that is not a coordinate pair.")
            if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                raise ZoneError(f"Zone '{name}' has a point outside the frame.")
            points.append([round(x, 4), round(y, 4)])

        entry = {"id": str(zone.get("id") or f"zone-{index}"), "name": name, "type": kind, "points": points}

        if kind == "watch":
            raw_seconds = zone.get("time_threshold")
            if not isinstance(raw_seconds, (int, float)) or isinstance(raw_seconds, bool):
                raise ZoneError(f"Zone '{name}': the watch time limit must be a number of seconds.")
            seconds = float(raw_seconds)
            if not (0.0 < seconds <= MAX_WATCH_SECONDS):
                raise ZoneError(f"Zone '{name}': the watch time limit must be between 0 and {int(MAX_WATCH_SECONDS)} seconds.")
            entry["time_threshold"] = round(seconds, 1)

        cleaned.append(entry)
    return cleaned


class ZoneSet:
    """Zones in pixel coordinates for one frame size, ready for per-frame checks."""

    def __init__(self, ignore: List[List[Point]], watch: List[Tuple[List[Point], float]]):
        self._ignore = ignore
        self._watch = watch

    @classmethod
    def from_config(cls, zones: List[Dict], width: int, height: int) -> "ZoneSet":
        ignore = []
        watch = []
        for zone in zones:
            polygon = [(x * width, y * height) for x, y in zone["points"]]
            if zone["type"] == "ignore":
                ignore.append(polygon)
            else:
                watch.append((polygon, float(zone["time_threshold"])))
        return cls(ignore, watch)

    def is_ignored(self, point: Point) -> bool:
        return any(_polygon_contains(point, polygon) for polygon in self._ignore)

    def time_limit(self, point: Point, default: float) -> float:
        """The time limit that applies at this point: the shortest watch limit containing it, else the default."""
        limits = [seconds for polygon, seconds in self._watch if _polygon_contains(point, polygon)]
        return min(limits) if limits else default

    def polygons(self) -> List[Tuple[str, List[Point]]]:
        """Pixel polygons with their kind, for drawing on the frame."""
        return [("ignore", p) for p in self._ignore] + [("watch", p) for p, _ in self._watch]

    @property
    def is_empty(self) -> bool:
        return not self._ignore and not self._watch
