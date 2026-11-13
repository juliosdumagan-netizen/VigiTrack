"""
Replays a labelled clip through both methods and scores them against ground truth.

A labelled clip (scenario file) is a dict:
    {
      "name": "...",
      "fps": 10,
      "frames": [{"t": 0.0, "dets": [{"id": 1, "class_name": "person", "box": [x1,y1,x2,y2]}, ...]}, ...],
      "events": [{"label": "unattended", "start": 13.6, "end": 45.0, "bag_id": 2}, ...]
    }

`events` are ground truth: the bag was genuinely unattended from `start` to `end`.
Frames carry already-tracked detections (the same dict shape
AdvancedBaggageMonitor.update() consumes), so evaluation needs no camera and no model.

Scoring rules (identical for both methods):
- An alert is a transition of the method's alert state to "on" for a bag.
- An event is detected if the method was alerting at the event start, or first
  turns alerting inside [start, end]. Latency = detection time − event start.
- An on-transition outside every event window is a false alarm.
- Recall = detected / events; false alarms per hour = false alarms / clip hours.
"""

from app.evaluation.baseline import StationaryTimerBaseline

_EPS = 1e-6


# ---------------------------------------------------------------------------
# Running a method over a clip
# ---------------------------------------------------------------------------

def run_frames(method, frames):
    """Replays frames through a method, returning its alert-state transitions."""
    transitions = []
    alerting = {}  # bag id -> last known alert state
    for frame in frames:
        t = float(frame["t"])
        for tel in method.update(frame["dets"], now=t):
            bag_id = tel["bag_id"]
            on = bool(tel["is_alert"])
            if on != alerting.get(bag_id, False):
                transitions.append({"bag_id": bag_id, "t": t, "on": on})
                alerting[bag_id] = on
    return transitions


def run_vigitrack(frames, distance_threshold: float = 150.0, time_threshold: float = 10.0):
    """Runs VigiTrack's ownership FSM (the system under evaluation)."""
    from app.detection.fsm_tracker import AdvancedBaggageMonitor
    monitor = AdvancedBaggageMonitor(distance_threshold=distance_threshold,
                                     time_threshold=time_threshold)
    return run_frames(monitor, frames)


def run_baseline(frames, time_threshold: float = 10.0):
    """Runs the naive stationary-timer baseline."""
    return run_frames(StationaryTimerBaseline(time_threshold=time_threshold), frames)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _matches(ev, bag_id) -> bool:
    return ev.get("bag_id") is None or ev["bag_id"] == bag_id


def _alerting_at_start(ev, transitions):
    """Returns the event start if the method was already alerting then, else None."""
    latest = None
    for tr in transitions:  # transitions are in clip time order
        if tr["t"] > ev["start"]:
            break
        if _matches(ev, tr["bag_id"]):
            latest = tr
    return ev["start"] if latest is not None and latest["on"] else None


def score(events, transitions, duration_seconds: float) -> dict:
    """Scores one method's transitions on one clip against the ground-truth events."""
    on_transitions = [tr for tr in transitions if tr["on"]]

    false_alarms = 0
    for tr in on_transitions:
        inside = any(
            _matches(ev, tr["bag_id"]) and ev["start"] - _EPS <= tr["t"] <= ev["end"] + _EPS
            for ev in events
        )
        if not inside:
            false_alarms += 1

    detected = 0
    missed = 0
    latencies = []
    for ev in events:
        at = _alerting_at_start(ev, transitions)
        if at is None:
            at = next(
                (tr["t"] for tr in on_transitions
                 if _matches(ev, tr["bag_id"]) and ev["start"] < tr["t"] <= ev["end"] + _EPS),
                None,
            )
        if at is None:
            missed += 1
        else:
            detected += 1
            latencies.append(at - ev["start"])

    hours = float(duration_seconds) / 3600.0
    return {
        "events": len(events),
        "detected": detected,
        "missed": missed,
        "recall": (detected / len(events)) if events else None,
        "false_alarms": false_alarms,
        "fa_per_hour": (false_alarms / hours) if hours > 0 else None,
        "mean_latency": (sum(latencies) / len(latencies)) if latencies else None,
        "latencies": latencies,
        "duration": float(duration_seconds),
    }


# ---------------------------------------------------------------------------
# Whole-set evaluation and reporting
# ---------------------------------------------------------------------------

def evaluate_scenarios(scenarios, distance_threshold: float = 150.0,
                       time_threshold: float = 10.0):
    """Runs both methods on every scenario and scores each."""
    results = []
    for sc in scenarios:
        frames = sc["frames"]
        events = list(sc.get("events", []))
        duration = float(frames[-1]["t"]) if frames else 0.0
        results.append({
            "name": sc["name"],
            "duration": duration,
            "events": events,
            "vigitrack": score(events, run_vigitrack(frames, distance_threshold, time_threshold), duration),
            "baseline": score(events, run_baseline(frames, time_threshold), duration),
        })
    return results


def aggregate(results, method: str) -> dict:
    """Sums a method's scores across every scenario."""
    total_events = total_detected = total_missed = total_fa = 0
    total_hours = 0.0
    all_latencies = []
    for r in results:
        s = r[method]
        total_events += s["events"]
        total_detected += s["detected"]
        total_missed += s["missed"]
        total_fa += s["false_alarms"]
        total_hours += s["duration"] / 3600.0
        all_latencies.extend(s["latencies"])
    return {
        "events": total_events,
        "detected": total_detected,
        "missed": total_missed,
        "recall": (total_detected / total_events) if total_events else None,
        "false_alarms": total_fa,
        "fa_per_hour": (total_fa / total_hours) if total_hours > 0 else None,
        "mean_latency": (sum(all_latencies) / len(all_latencies)) if all_latencies else None,
        "hours": total_hours,
    }


def _fmt(value, kind: str) -> str:
    if value is None:
        return "-"
    if kind == "pct":
        return f"{value * 100:.0f}%"
    if kind == "rate":
        return f"{value:.1f}"
    return f"{value:.1f}"


def format_report(results) -> str:
    """Renders the comparison table: one row per scenario per method, plus totals."""
    header = (f"{'Scenario':<22} {'Method':<16} {'Events':>6} {'Detected':>8} "
              f"{'Missed':>6} {'Recall':>6} {'FA':>4} {'FA/h':>7} {'Latency s':>9}")
    lines = [header, "-" * len(header)]

    for r in results:
        for key, label in (("vigitrack", "VigiTrack"), ("baseline", "Stationary")):
            s = r[key]
            lines.append(
                f"{r['name']:<22} {label:<16} {s['events']:>6} {s['detected']:>8} "
                f"{s['missed']:>6} {_fmt(s['recall'], 'pct'):>6} {s['false_alarms']:>4} "
                f"{_fmt(s['fa_per_hour'], 'rate'):>7} {_fmt(s['mean_latency'], 'num'):>9}"
            )
    lines.append("-" * len(header))
    for key, label in (("vigitrack", "TOTAL VigiTrack"), ("baseline", "TOTAL Stationary")):
        a = aggregate(results, key)
        lines.append(
            f"{label:<22} {'':<16} {a['events']:>6} {a['detected']:>8} "
            f"{a['missed']:>6} {_fmt(a['recall'], 'pct'):>6} {a['false_alarms']:>4} "
            f"{_fmt(a['fa_per_hour'], 'rate'):>7} {_fmt(a['mean_latency'], 'num'):>9}"
        )
    lines.append("")
    lines.append(f"Total footage: {sum(r['duration'] for r in results):.0f} s "
                 f"({sum(r['duration'] for r in results) / 3600.0:.3f} h), "
                 f"{len(results)} scenario(s).")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Scenario file I/O
# ---------------------------------------------------------------------------

def load_scenario(path) -> dict:
    import json
    with open(path, encoding="utf-8") as f:
        sc = json.load(f)
    for key in ("name", "frames"):
        if key not in sc:
            raise ValueError(f"{path}: scenario file is missing '{key}'.")
    sc.setdefault("events", [])
    if not sc["frames"]:
        raise ValueError(f"{path}: scenario has no frames.")
    return sc


def save_scenario(scenario: dict, path) -> None:
    import json
    with open(path, "w", encoding="utf-8") as f:
        json.dump(scenario, f, indent=1)
