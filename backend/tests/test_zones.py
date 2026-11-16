import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, REPO)

from app.detection.fsm_tracker import AdvancedBaggageMonitor, BaggageState
from app.detection.zones import ZoneError, ZoneSet, _polygon_contains, normalise_zones

results = []
def check(name, cond, extra: object = ""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra else ""))

SQUARE = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
check("point inside square", _polygon_contains((0.5, 0.5), SQUARE))
check("point outside square", not _polygon_contains((1.5, 0.5), SQUARE))
L_SHAPE = [(0, 0), (4, 0), (4, 1), (1, 1), (1, 4), (0, 4)]
check("concave polygon: notch is outside", not _polygon_contains((3, 3), L_SHAPE) and _polygon_contains((0.5, 3), L_SHAPE))

def zone(kind="ignore", points=None, seconds=None, name=None):
    z = {"type": kind, "points": points or [[0.0, 0.0], [0.3, 0.0], [0.3, 0.3], [0.0, 0.3]]}
    if seconds is not None:
        z["time_threshold"] = seconds
    if name is not None:
        z["name"] = name
    return z

def rejects(raw, fragment):
    try:
        normalise_zones(raw)
        return False
    except ZoneError as e:
        return fragment in str(e)

valid = normalise_zones([zone(name="Desk"), zone("watch", seconds=3, name="Door")])
check("valid zones are accepted", len(valid) == 2 and valid[0]["name"] == "Desk")
check("watch zone keeps its time limit", valid[1]["time_threshold"] == 3.0)
check("unnamed zone gets a default name", normalise_zones([zone()])[0]["name"] == "Zone 1")
check("unknown type is rejected", rejects([zone("block")], "type must be ignore or watch"))
check("fewer than three points is rejected", rejects([zone(points=[[0, 0], [1, 1]])], "at least three points"))
check("point outside the frame is rejected", rejects([zone(points=[[0, 0], [1.2, 0], [0, 1]])], "outside the frame"))
check("non-numeric point is rejected", rejects([zone(points=[[0, 0], ["a", 1], [0, 1]])], "coordinate pair"))
check("watch zone needs a time limit", rejects([zone("watch", name="Door")], "watch time limit must be a number"))
check("watch limit above one hour is rejected", rejects([zone("watch", seconds=7200, name="Door")], "between 0 and 3600"))
check("too many zones is rejected", rejects([zone() for _ in range(21)], "at most 20"))
check("non-list is rejected", rejects({"type": "ignore"}, "must be a list"))

zs = ZoneSet.from_config([zone(name="A"), zone("watch", seconds=2), zone("watch", seconds=5, points=[[0, 0], [1, 0], [1, 1]])], 1000, 1000)
check("pixel conversion: ignore zone covers 0..300", zs.is_ignored((150, 150)) and not zs.is_ignored((400, 400)))
check("watch limit: shortest containing zone wins", zs.time_limit((100, 100), 10.0) == 2.0)
check("watch limit: default outside every watch zone", zs.time_limit((100, 900), 10.0) == 10.0)

# --- FSM behaviour ---
def run_scenario(bag_box, person_near, person_far, zones=None, seconds=20.0, time_threshold=10.0):
    """Owner stands near the bag, then walks far away. Returns the states seen, and the time of the first alert."""
    mon = AdvancedBaggageMonitor(distance_threshold=150, time_threshold=time_threshold)
    if zones is not None:
        mon.set_zones(ZoneSet.from_config(zones, 1000, 1000))
    bag = {"id": 1, "class_name": "backpack", "box": bag_box, "confidence": 0.9}
    near = {"id": 2, "class_name": "person", "box": person_near, "confidence": 0.9}
    far = {"id": 2, "class_name": "person", "box": person_far, "confidence": 0.9}
    t = 0.0
    for _ in range(4):
        mon.update([bag, near], now=t)
        t += 0.1
    states, first_alert, t = [], None, 0.5
    while t <= seconds:
        out = mon.update([bag, far], now=t)
        if out:
            states.append(out[0]["state"])
            if out[0]["is_alert"] and first_alert is None:
                first_alert = t
        t += 0.5
    return states, first_alert, mon

BAG_OUTSIDE = [480, 480, 520, 520]
NEAR_OUTSIDE = [460, 440, 540, 560]
FAR = [900, 100, 940, 200]

states, alert_at, _ = run_scenario(BAG_OUTSIDE, NEAR_OUTSIDE, FAR)
check("baseline: unattended bag alerts after the global limit", alert_at is not None and 9.5 <= alert_at <= 11.0, alert_at)

ignore_here = [zone(points=[[0.4, 0.4], [0.7, 0.4], [0.7, 0.7], [0.4, 0.7]])]
states, alert_at, _ = run_scenario(BAG_OUTSIDE, NEAR_OUTSIDE, FAR, zones=ignore_here)
check("ignore zone: bag inside it never alerts", alert_at is None and states == [], states[:3])

ignore_only_person = [zone(points=[[0.45, 0.45], [0.6, 0.45], [0.6, 0.6], [0.45, 0.6]])]
bag_beside = [400, 450, 440, 490]
person_in_zone = [450, 440, 490, 500]
mon = AdvancedBaggageMonitor(distance_threshold=150, time_threshold=10)
mon.set_zones(ZoneSet.from_config(ignore_only_person, 1000, 1000))
bag = {"id": 1, "class_name": "backpack", "box": bag_beside, "confidence": 0.9}
person = {"id": 2, "class_name": "person", "box": person_in_zone, "confidence": 0.9}
owner_out: list = []
for i in range(4):
    owner_out = mon.update([bag, person], now=i * 0.1)
check("person inside an ignore zone still counts as owner",
      bool(owner_out) and owner_out[0]["state"] == BaggageState.STATIC_ATTENDED.value,
      owner_out[0]["state"] if owner_out else None)

watch_here = [zone("watch", seconds=2.0, points=[[0.4, 0.4], [0.7, 0.4], [0.7, 0.7], [0.4, 0.7]])]
watch_elsewhere = [zone("watch", seconds=2.0, points=[[0.8, 0.8], [0.95, 0.8], [0.95, 0.95], [0.8, 0.95]])]
states, alert_at, _ = run_scenario(BAG_OUTSIDE, NEAR_OUTSIDE, FAR, zones=watch_elsewhere)
check("watch zone: bag outside it still uses the global limit", alert_at is not None and alert_at >= 9.5, alert_at)

bag_in_watch = [480, 480, 520, 520]
states, alert_at, _ = run_scenario(bag_in_watch, NEAR_OUTSIDE, FAR, zones=watch_here)
check("watch zone: bag inside it alerts at its own limit, about 2 s", alert_at is not None and 2.0 <= alert_at <= 3.5, alert_at)

passed = sum(1 for _, ok in results if ok)
print(f"\n{passed}/{len(results)} checks passed")
