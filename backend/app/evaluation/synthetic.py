"""
Synthetic scenario set: five labelled clips built from deterministic box tracks.

These are SMOKE scenarios, not the labelled real-footage set (NFR-31). They exist so
the evaluation harness has known ground truth before any footage is recorded, and so
regression tests can pin down both methods' behaviour. Real clips come from
`python -m app.evaluation.cli record-video` and manual event labelling.

Scenario geometry (canvas 1280x720, 10 fps):
- Bag centroid sits at (600, 400); person box centroid y is also 400, so the
  person-bag distance is a pure horizontal gap. The ownership threshold is 150 px.
- Person walks at 60 px/s (6 px/frame). The owner crosses the 150 px threshold
  3.5 s after starting to walk away (210 px from x1=500 to x1=710).

Ground truth: a bag is "unattended" from the moment its owner is farther than the
150 px threshold (or leaves it behind) until the end of the clip.
"""

W, H = 1280, 720
FPS = 10
STEP = 1.0 / FPS
WALK_PX_PER_S = 60.0
DISTANCE_THRESHOLD = 150.0

# Analytic event starts (see module docstring):
# - walk-away cases: walk starts at t=10, threshold crossed at 10 + 3.5 -> 13.6 (first frame grid point past 13.5)
WALK_EVENT_START = 13.6
# - abandoned bag: put-down at t=15, person walking left from x1=200 crosses the
#   threshold (bag centroid 145, person centroid x1+40) at x1 < -45 -> t = 19.1
ABANDON_EVENT_START = 19.1


def _person(x1: float, pid: int = 1):
    return {"id": pid, "class_name": "person", "box": [x1, 250, x1 + 80, 550]}


def _bag(x1: float, bid: int = 2):
    return {"id": bid, "class_name": "backpack", "box": [x1, 365, x1 + 70, 435]}


def _grid(duration_s: float):
    n = int(round(duration_s * FPS))
    for i in range(n + 1):
        yield round(i * STEP, 1)


def seated_reader() -> dict:
    """Owner sits beside a motionless bag for the whole clip. No unattended event."""
    frames = [{"t": t, "dets": [_person(500), _bag(565)]} for t in _grid(45.0)]
    return {"name": "seated_reader", "fps": FPS,
            "description": "Owner seated next to a static bag; nothing is unattended.",
            "events": [], "frames": frames}


def owner_walks_away() -> dict:
    """Owner stands up at t=10 and walks a few metres away, staying visible."""
    frames = []
    for t in _grid(45.0):
        x1 = 500.0 if t < 10.0 else min(500.0 + WALK_PX_PER_S * (t - 10.0), 910.0)
        frames.append({"t": t, "dets": [_person(x1), _bag(565)]})
    return {"name": "owner_walks_away", "fps": FPS,
            "description": "Owner walks away but remains in frame, far from the bag.",
            "events": [{"label": "unattended", "start": WALK_EVENT_START, "end": 45.0, "bag_id": 2}],
            "frames": frames}


def owner_leaves_frame() -> dict:
    """Owner stands up at t=10 and walks out of the camera view entirely."""
    frames = []
    for t in _grid(45.0):
        dets = [_bag(565)]
        if t < 10.0:
            dets.insert(0, _person(500))
        else:
            x1 = 500.0 + WALK_PX_PER_S * (t - 10.0)
            if x1 < W:  # still (partially) visible
                dets.insert(0, _person(x1))
        frames.append({"t": t, "dets": dets})
    return {"name": "owner_leaves_frame", "fps": FPS,
            "description": "Owner walks out of view, leaving the bag behind.",
            "events": [{"label": "unattended", "start": WALK_EVENT_START, "end": 45.0, "bag_id": 2}],
            "frames": frames}


def passer_by() -> dict:
    """Owner stays seated; a stranger walks past the bag. Nothing is unattended."""
    frames = []
    for t in _grid(50.0):
        dets = [_person(500), _bag(565)]
        if 15.0 < t < 37.7:
            # Stranger crosses right-to-left on a nearer/different line, closest
            # approach is ~130 px from the bag (within the 150 px threshold).
            x1 = 1280.0 - WALK_PX_PER_S * (t - 15.0)
            if x1 > -80.0:
                dets.append({"id": 3, "class_name": "person", "box": [x1, 120, x1 + 80, 420]})
        frames.append({"t": t, "dets": dets})
    return {"name": "passer_by", "fps": FPS,
            "description": "Owner seated; a stranger passes close to the attended bag.",
            "events": [], "frames": frames}


def abandoned_bag() -> dict:
    """Owner carries the bag in, puts it down at t=15 and walks off."""
    frames = []
    for t in _grid(50.0):
        dets = []
        if t <= 15.0:
            x1 = 1100.0 - WALK_PX_PER_S * t          # walking left, carrying the bag
            dets = [_person(x1), _bag(x1 - 90)]
        else:
            x1 = 200.0 - WALK_PX_PER_S * (t - 15.0)  # keeps walking, bag stays put
            if x1 + 80 > 0.0:
                dets.append(_person(x1))
            dets.append(_bag(110))
        frames.append({"t": t, "dets": dets})
    return {"name": "abandoned_bag", "fps": FPS,
            "description": "Owner carries the bag in, sets it down and leaves.",
            "events": [{"label": "unattended", "start": ABANDON_EVENT_START, "end": 50.0, "bag_id": 2}],
            "frames": frames}


def build_synthetic_set():
    """Returns the five scenario dicts, freshly built (each call returns new data)."""
    return [seated_reader(), owner_walks_away(), owner_leaves_frame(),
            passer_by(), abandoned_bag()]
