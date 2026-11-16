import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, REPO)

from app.detection.classes import BAG_CLASSES, CROSS_BAG_CLASSES, SUPPORTED_CLASSES
from app.detection.fsm_tracker import AdvancedBaggageMonitor
from app.evaluation.evaluate import aggregate, evaluate_scenarios
from app.evaluation.synthetic import as_laptops, build_synthetic_set

results = []
def check(name, cond, extra: object = ""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra else ""))

# --- 1. Class configuration ---
check("laptop is COCO class 63", SUPPORTED_CLASSES.get(63) == "laptop")
check("laptop is a bag class for the FSM", "laptop" in BAG_CLASSES)
check("laptop is not in the cross-bag group", "laptop" not in CROSS_BAG_CLASSES)
check("existing bag classes are unchanged", set(CROSS_BAG_CLASSES) == {"backpack", "handbag", "suitcase"})

# --- 2. FSM handles a laptop like a bag ---
def box(x1, y1, w, h):
    return [x1, y1, x1 + w, y1 + h]

def det(i, cls, b):
    return {"id": i, "class_name": cls, "box": b, "confidence": 0.9}

def walk_away_with(cls, time_threshold=10.0):
    mon = AdvancedBaggageMonitor(distance_threshold=150, time_threshold=time_threshold)
    bag = box(480, 480, 60, 60)
    near = box(440, 440, 100, 160)
    far = box(900, 100, 80, 160)
    t = 0.0
    for _ in range(4):
        mon.update([det(1, cls, bag), det(2, "person", near)], now=t)
        t += 0.1
    alert_at = None
    t = 0.5
    while t <= 20.0:
        out = mon.update([det(1, cls, bag), det(2, "person", far)], now=t)
        if out and out[0]["is_alert"] and alert_at is None:
            alert_at = t
        t += 0.5
    return alert_at

laptop_alert = walk_away_with("laptop")
backpack_alert = walk_away_with("backpack")
check("laptop left behind raises an alert", laptop_alert is not None and 9.5 <= laptop_alert <= 11.0, laptop_alert)
check("laptop alert timing matches a backpack", laptop_alert == backpack_alert, (laptop_alert, backpack_alert))

# A laptop must not inherit a backpack's track, or the bag's ownership history would transfer to it.
mon = AdvancedBaggageMonitor()
spot = box(300, 300, 60, 60)
mon.update([det(1, "backpack", spot)], now=0.0)
mon.update([], now=0.1)
mon.update([det(9, "laptop", spot)], now=0.2)
check("laptop does not take over a backpack's track", 9 in mon.baggage_pool and 1 in mon.baggage_pool,
      sorted(mon.baggage_pool))

mon = AdvancedBaggageMonitor()
mon.update([det(1, "backpack", spot)], now=0.0)
mon.update([], now=0.1)
mon.update([det(9, "handbag", spot)], now=0.2)
check("control: a handbag does take over the backpack's track", 1 in mon.baggage_pool and 9 not in mon.baggage_pool,
      sorted(mon.baggage_pool))

# --- 3. Measured on the synthetic scenario set ---
bag_set = build_synthetic_set()
laptop_set = as_laptops(build_synthetic_set())
bag_results = evaluate_scenarios(bag_set)
laptop_results = evaluate_scenarios(laptop_set)

for method in ("vigitrack", "baseline"):
    a = aggregate(bag_results, method)
    b = aggregate(laptop_results, method)
    same = (a["events"], a["detected"], a["false_alarms"], a["mean_latency"]) == \
           (b["events"], b["detected"], b["false_alarms"], b["mean_latency"])
    check(f"{method}: laptop clips give the same results as bag clips", same,
          f"bag FA={a['false_alarms']} recall={a['detected']}/{a['events']}; "
          f"laptop FA={b['false_alarms']} recall={b['detected']}/{b['events']}")

vt = aggregate(laptop_results, "vigitrack")
check("vigitrack on laptop clips: all 3 unattended events detected, no false alarms",
      vt["detected"] == 3 and vt["false_alarms"] == 0, (vt["detected"], vt["false_alarms"]))

# --- 4. Upstream detector stabilizer and deduplicator do not merge laptop with bag classes ---
from app.detection.detector import ObjectDetector, SpatialIdentityStabilizer

stab = SpatialIdentityStabilizer()
first = stab.stabilize([{"class_name": "backpack", "box": spot, "confidence": 0.8}])
second = stab.stabilize([{"class_name": "laptop", "box": spot, "confidence": 0.8}])
check("stabilizer gives laptop a distinct canonical track from backpack at same box",
      first[0]["id"] != second[0]["id"] and second[0]["class_name"] == "laptop",
      (first[0]["id"], second[0]["id"], second[0]["class_name"]))

dedup_laptop = ObjectDetector._deduplicate_boxes(
    None,  # type: ignore[arg-type]
    [
        {"class_name": "backpack", "box": spot, "confidence": 0.9},
        {"class_name": "laptop", "box": spot, "confidence": 0.8},
    ],
)
check("deduplicate keeps overlapping backpack and laptop",
      len(dedup_laptop) == 2, [d["class_name"] for d in dedup_laptop])

dedup_bags = ObjectDetector._deduplicate_boxes(
    None,  # type: ignore[arg-type]
    [
        {"class_name": "backpack", "box": spot, "confidence": 0.9},
        {"class_name": "handbag", "box": spot, "confidence": 0.8},
    ],
)
check("deduplicate still suppresses overlapping backpack and handbag",
      len(dedup_bags) == 1, [d["class_name"] for d in dedup_bags])

# --- 5. Cell phone opt-in class & detection refinements ---
check("cell phone is COCO class 67", SUPPORTED_CLASSES.get(67) == "cell phone")
check("cell phone is a bag/item class for the FSM", "cell phone" in BAG_CLASSES)
check("cell phone is excluded from cross-bag merging", "cell phone" not in CROSS_BAG_CLASSES)

stab_phone = SpatialIdentityStabilizer()
p1 = stab_phone.stabilize([{"class_name": "backpack", "box": spot, "confidence": 0.8}])
p2 = stab_phone.stabilize([{"class_name": "cell phone", "box": spot, "confidence": 0.8}])
check("stabilizer keeps cell phone distinct from backpack",
      p1[0]["id"] != p2[0]["id"] and p2[0]["class_name"] == "cell phone")

# Global best IoU matching prevents det 0 from stealing track 1 when det 1 overlaps it much better.
stab_global = SpatialIdentityStabilizer()
init = stab_global.stabilize([
    {"class_name": "person", "box": [100.0, 100.0, 180.0, 300.0], "confidence": 0.9},
])
t1_id = init[0]["id"]
next_frame = stab_global.stabilize([
    {"class_name": "person", "box": [140.0, 100.0, 220.0, 300.0], "confidence": 0.9},  # lower IoU with track 1
    {"class_name": "person", "box": [102.0, 100.0, 182.0, 300.0], "confidence": 0.9},  # high IoU with track 1
])
check("global stabilizer matching avoids ID swap on crossing boxes",
      next_frame[1]["id"] == t1_id and next_frame[0]["id"] != t1_id,
      [d["id"] for d in next_frame])

dummy_det = ObjectDetector.__new__(ObjectDetector)
check("geometry rejects tiny low-confidence backpack speckle",
      not dummy_det._filter_object_geometry("backpack", [0.0, 0.0, 8.0, 8.0], 0.30))
check("geometry rejects extreme sliver false positive",
      not dummy_det._filter_object_geometry("suitcase", [0.0, 0.0, 10.0, 120.0], 0.40))
check("geometry keeps valid small cell phone box",
      dummy_det._filter_object_geometry("cell phone", [10.0, 10.0, 24.0, 34.0], 0.30))

passed = sum(1 for _, ok in results if ok)
print(f"\n{passed}/{len(results)} checks passed")
