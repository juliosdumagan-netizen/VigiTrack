"""
Phase 3 checks: the evaluation harness itself — synthetic scenario set,
stationary-timer baseline, scoring math, and the both-methods comparison run.
Pure Python: no camera, no model, no Flask. Run from the backend folder:
    python tests/test_evaluation.py
"""
import os
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, REPO)

from app.evaluation.baseline import StationaryTimerBaseline  # noqa: E402
from app.evaluation.evaluate import (  # noqa: E402
    aggregate,
    evaluate_scenarios,
    format_report,
    load_scenario,
    run_baseline,
    run_vigitrack,
    save_scenario,
    score,
)
from app.evaluation.synthetic import build_synthetic_set  # noqa: E402

results = []


def check(name, cond, extra=""):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra else ""))


# --- 1. Synthetic scenario set ---
set_ = build_synthetic_set()
names = [s["name"] for s in set_]
check("synthetic set has the five roadmap scenarios",
      names == ["seated_reader", "owner_walks_away", "owner_leaves_frame", "passer_by", "abandoned_bag"],
      str(names))

check("seated reader and passer-by clips have no unattended events",
      next(s for s in set_ if s["name"] == "seated_reader")["events"] == []
      and next(s for s in set_ if s["name"] == "passer_by")["events"] == [])

walk = next(s for s in set_ if s["name"] == "owner_walks_away")
leave = next(s for s in set_ if s["name"] == "owner_leaves_frame")
aban = next(s for s in set_ if s["name"] == "abandoned_bag")
check("walk-away and leave-frame clips label one event starting at the 150 px crossing",
      len(walk["events"]) == 1 and walk["events"][0]["start"] == 13.6
      and len(leave["events"]) == 1 and leave["events"][0]["start"] == 13.6)
check("abandoned-bag clip labels one event starting when the owner passes 150 px away",
      len(aban["events"]) == 1 and aban["events"][0]["start"] == 19.1)
check("every scenario has frames on a 0.1 s grid",
      all(len(s["frames"]) == round(s["frames"][-1]["t"] * 10) + 1 for s in set_))

# --- 2. Methods on the attended-reading clip ---
seated = next(s for s in set_ if s["name"] == "seated_reader")
vt_seated = run_vigitrack(seated["frames"])
bl_seated = run_baseline(seated["frames"])
check("VigiTrack raises no alert while the owner sits with the bag", vt_seated == [], str(vt_seated))
check("baseline raises exactly one alert on the static attended bag",
      len(bl_seated) == 1 and bl_seated[0]["on"] and abs(bl_seated[0]["t"] - 10.0) < 1e-6,
      str(bl_seated))

s = score(seated["events"], bl_seated, 45.0)
check("that baseline alert is counted as a false alarm",
      s["false_alarms"] == 1 and s["events"] == 0, str(s))

# --- 3. Both methods over the whole set ---
full = evaluate_scenarios(set_, distance_threshold=150.0, time_threshold=10.0)
vt = aggregate(full, "vigitrack")
bl = aggregate(full, "baseline")

check("VigiTrack detects every labelled event (recall 100%)",
      vt["events"] == 3 and vt["detected"] == 3 and vt["missed"] == 0 and vt["recall"] == 1.0, str(vt))
check("VigiTrack raises no false alarms on the set", vt["false_alarms"] == 0 and vt["fa_per_hour"] == 0.0)
check("VigiTrack alert latency equals the time threshold",
      vt["mean_latency"] is not None and abs(vt["mean_latency"] - 10.0) <= 0.2, str(vt["mean_latency"]))
check("baseline detects every labelled event too", bl["recall"] == 1.0 and bl["missed"] == 0, str(bl))
check("baseline false alarms on every attended-static clip (4 total)", bl["false_alarms"] == 4, str(bl))
check("baseline false-alarm rate per hour is higher than VigiTrack's",
      bl["fa_per_hour"] > vt["fa_per_hour"], f"{bl['fa_per_hour']} vs {vt['fa_per_hour']}")

walk_result = next(r for r in full if r["name"] == "owner_walks_away")
check("baseline was already alerting when the walk-away event began (latency 0)",
      walk_result["baseline"]["latencies"] == [0.0], str(walk_result["baseline"]["latencies"]))
check("VigiTrack alerts one time threshold after the owner separates",
      abs(walk_result["vigitrack"]["latencies"][0] - 10.0) <= 0.2,
      str(walk_result["vigitrack"]["latencies"]))
check("VigiTrack raises exactly one alert transition per unattended episode",
      len(run_vigitrack(walk["frames"])) == 1)

# --- 4. Scoring math, on hand-made data ---
HOUR_EVENTS = [{"start": 10.0, "end": 20.0, "bag_id": 1}]

s = score(HOUR_EVENTS, [{"bag_id": 1, "t": 15.0, "on": True}], 3600.0)
check("alert inside the window is a detection with correct latency",
      s["detected"] == 1 and s["latencies"] == [5.0] and s["false_alarms"] == 0
      and s["fa_per_hour"] == 0.0 and s["recall"] == 1.0, str(s))

s = score(HOUR_EVENTS, [{"bag_id": 1, "t": 5.0, "on": True}, {"bag_id": 1, "t": 25.0, "on": True}], 3600.0)
check("alerts before and after the window are false alarms, early alert still detects",
      s["false_alarms"] == 2 and s["detected"] == 1 and s["latencies"] == [0.0]
      and s["fa_per_hour"] == 2.0, str(s))

s = score(HOUR_EVENTS, [{"bag_id": 2, "t": 15.0, "on": True}], 3600.0)
check("an alert for a different bag does not count (event missed, alert false)",
      s["detected"] == 0 and s["missed"] == 1 and s["false_alarms"] == 1, str(s))

s = score(HOUR_EVENTS, [{"bag_id": 1, "t": 8.0, "on": True}, {"bag_id": 1, "t": 9.0, "on": False}], 3600.0)
check("alert that ends before the event does not detect it",
      s["missed"] == 1 and s["false_alarms"] == 1, str(s))

s = score([{"start": 10.0, "end": 20.0}], [{"bag_id": 7, "t": 15.0, "on": True}], 1800.0)
check("an event with no bag id matches any bag",
      s["detected"] == 1 and s["latencies"] == [5.0], str(s))

# --- 5. Baseline re-arms when the object moves ---
b = StationaryTimerBaseline(time_threshold=1.0, static_tolerance_px=3.0)
static = [{"id": 1, "class_name": "backpack", "box": [0, 0, 70, 70]}]
moved = [{"id": 1, "class_name": "backpack", "box": [40, 0, 110, 70]}]
seq = [(0.0, static), (0.5, static), (1.0, static),      # still -> alert on at 1.0
       (1.1, moved), (1.6, moved), (2.1, moved)]         # moved -> off, then on again at 2.1
transitions = []
prev = False
for t, dets in seq:
    on = b.update(dets, now=t)[0]["is_alert"]
    if on != prev:
        transitions.append({"t": t, "on": on})
        prev = on
check("baseline alert clears and re-arms when the object moves",
      transitions == [{"t": 1.0, "on": True}, {"t": 1.1, "on": False}, {"t": 2.1, "on": True}],
      str(transitions))

# --- 6. Report and file I/O ---
report = format_report(full)
check("report shows totals for both methods",
      "TOTAL VigiTrack" in report and "TOTAL Stationary" in report and "Total footage" in report)
check("aggregate counts the set's footage", abs(aggregate(full, "vigitrack")["hours"] - 235 / 3600) < 1e-9)

tmp = tempfile.mkdtemp(prefix="vt_eval_")
path = os.path.join(tmp, "clip.json")
save_scenario(seated, path)
loaded = load_scenario(path)
check("scenario save/load roundtrip preserves frames and events",
      loaded["frames"] == seated["frames"] and loaded["events"] == seated["events"]
      and loaded["name"] == "seated_reader")

try:
    load_scenario(os.path.join(tmp, "missing.json"))
    check("loading a missing scenario file raises", False)
except FileNotFoundError:
    check("loading a missing scenario file raises", True)

passed = sum(results)
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
