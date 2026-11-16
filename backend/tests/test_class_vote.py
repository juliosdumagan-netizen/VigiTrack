import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, REPO)

from app.detection.class_vote import ClassHistory, class_stability

results = []
def check(name, cond, extra: object = ""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra else ""))

# --- 1. Voting on one track ---
h = ClassHistory()
for _ in range(10):
    h.add("suitcase", 0.30)
for _ in range(4):
    h.add("handbag", 0.20)
check("majority class wins", h.dominant() == "suitcase", h.dominant())

h = ClassHistory()
h.add("handbag", 0.3)
h.add("suitcase", 0.3)
check("tie goes to the most recent class", h.dominant() == "suitcase", h.dominant())

h = ClassHistory()
for _ in range(6):
    h.add("suitcase", 0.26)
for _ in range(5):
    h.add("backpack", 0.72)
check("higher-confidence frames outweigh more weak frames", h.dominant() == "backpack", h.dominant())

h = ClassHistory(maxlen=5)
for _ in range(5):
    h.add("handbag", 0.2)
for _ in range(3):
    h.add("backpack", 0.3)
check("old observations fall out of the window", h.dominant() == "backpack"
      and h.evidence()["handbag"]["frames"] == 2 and h.evidence()["backpack"]["frames"] == 3, h.evidence())

check("empty history has no class", ClassHistory().dominant() is None)

h = ClassHistory()
for conf in (0.21, 0.35, 0.28):
    h.add("suitcase", conf)
h.add("handbag", 0.19)
ev = h.evidence()
check("evidence counts frames per class", ev["suitcase"]["frames"] == 3 and ev["handbag"]["frames"] == 1, ev)
check("evidence keeps the best confidence per class", ev["suitcase"]["max_confidence"] == 0.35, ev["suitcase"])

# --- 2. Stability measurement ---
s = class_stability(["suitcase"] * 8 + ["handbag"] * 2)
check("stability: dominant label and agreement", s["dominant"] == "suitcase" and abs(s["agreement"] - 0.8) < 1e-9, s)
check("stability: empty track is handled", class_stability([])["frames"] == 0)

# --- 3. The real stabilizer, fed the screenshot case: a pouch that flickers between classes ---
from app.detection.detector import SpatialIdentityStabilizer

stab = SpatialIdentityStabilizer(max_lost_frames=45, max_centroid_dist=85.0, min_iou=0.30)
box = [300.0, 240.0, 560.0, 480.0]
labels = ["suitcase"] * 9 + ["handbag"] * 3 + ["suitcase"] * 2
out: list = []
for label in labels:
    out = stab.stabilize([{"class_name": label, "box": box, "confidence": 0.3 if label == "suitcase" else 0.2}])

check("stabilizer keeps one track for the flickering object", len({d["id"] for d in out}) == 1 and out[0]["id"] == 1)
check("stabilizer outputs the voted class", out[0]["class_name"] == "suitcase", out[0]["class_name"])
check("stabilizer keeps the raw label of the last frame", out[0]["raw_class"] == "suitcase")
check("stabilizer exposes evidence for each class", out[0]["class_evidence"]["handbag"]["frames"] == 3
      and out[0]["class_evidence"]["suitcase"]["frames"] == 11, out[0]["class_evidence"])

passed = sum(1 for _, ok in results if ok)
print(f"\n{passed}/{len(results)} checks passed")
