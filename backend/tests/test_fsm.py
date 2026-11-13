"""
Scenario tests for the ownership and alert state machine (fsm_tracker.py).
Uses a simulated clock, so timing is deterministic. Run from the backend folder:
    python tests/test_fsm.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.detection.fsm_tracker import AdvancedBaggageMonitor  # noqa: E402

results = []


def check(name, cond, extra=""):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra else ""))


def person_at(pid, cx, cy, w=100, h=300):
    """A person box centred on (cx, cy)."""
    return {"id": pid, "class_name": "person", "box": [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2],
            "confidence": 0.9}


def bag_at(bid, cx, cy, w=40, h=60, cls="handbag"):
    """A bag box centred on (cx, cy)."""
    return {"id": bid, "class_name": cls, "box": [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2],
            "confidence": 0.8}


OWNER_NEAR = (50, 150)      # owner centre
OWNER_FAR = (950, 150)      # owner centre, well beyond the threshold
BAG_CX, BAG_CY = 120, 260   # bag centre, about 130 px from the owner


def owner(cx_cy):
    return person_at(1, *cx_cy)


def run(monitor, frames, start, dt):
    """Feeds one detection list per frame. Returns the last telemetry and the end time."""
    t = start
    last = []
    for dets in frames:
        last = monitor.update(dets, now=t)
        t += dt
    return last, t


def telemetry_for(items, bid):
    return next((i for i in items if i["bag_id"] == bid), None)


# --- 1. Seated owner keeps the bag attended (regression) ---
m = AdvancedBaggageMonitor(distance_threshold=150, time_threshold=10)
states = []
t = 1000.0
for _ in range(60):
    out = m.update([owner(OWNER_NEAR), bag_at(10, BAG_CX, BAG_CY)], now=t)
    t += 0.1
    tel = telemetry_for(out, 10)
    if tel:
        states.append(tel["state"])
check("seated owner: bag becomes attended", states and states[-1] in ("STATIC_ATTENDED", "CARRIED"),
      states[-1] if states else "none")
check("seated owner: never alerts", "UNATTENDED_ALERT" not in states)

# --- 2. Abandoned bag with no owner alerts after the time threshold ---
m = AdvancedBaggageMonitor(distance_threshold=150, time_threshold=10)
out, t = run(m, [[bag_at(20, BAG_CX, BAG_CY)] for _ in range(3)], 2000.0, 0.1)
out, t = run(m, [[bag_at(20, BAG_CX, BAG_CY)] for _ in range(120)], t, 0.1)
tel = telemetry_for(out, 20)
check("abandoned bag with no owner raises alert", tel and tel["state"] == "UNATTENDED_ALERT",
      tel["state"] if tel else "none")

# --- 3. Passer-by cannot take over a moving bag in a few frames (O-1) ---
m = AdvancedBaggageMonitor(distance_threshold=150, time_threshold=10, takeover_confirm_frames=10)
out, t = run(m, [[owner(OWNER_NEAR), bag_at(30, BAG_CX, BAG_CY)] for _ in range(5)], 3000.0, 0.1)
check("owner links bag before leaving", m.baggage_pool[30].owner_id == 1)

# The owner leaves the frame. The bag starts moving 20 px per frame. A passer-by walks
# beside it, 30 px to the right, which is inside the 75 px takeover zone.
def walker_frames(bid, start_step, count):
    frames = []
    for i in range(count):
        cx = BAG_CX + 20 * (start_step + i)
        frames.append([bag_at(bid, cx, BAG_CY), person_at(2, cx + 30, BAG_CY)])
    return frames


out, t = run(m, walker_frames(30, 1, 5), t, 0.1)
check("passer-by is counted toward takeover", m.baggage_pool[30].retrieval_streaks.get(2) == 5,
      str(m.baggage_pool[30].retrieval_streaks))
check("passer-by for 5 frames does not take over (O-1)", m.baggage_pool[30].owner_id == 1,
      f"owner_id={m.baggage_pool[30].owner_id}")

out, t = run(m, walker_frames(30, 6, 6), t, 0.1)
check("passer-by staying beside a moving bag is confirmed as owner after 10 frames",
      m.baggage_pool[30].owner_id == 2, f"owner_id={m.baggage_pool[30].owner_id}")
tel = telemetry_for(out, 30)
check("confirmed takeover shows the bag as CARRIED", tel and tel["state"] == "CARRIED",
      tel["state"] if tel else "none")

# --- 4. Pending takeover is cleared when nobody is near ---
m = AdvancedBaggageMonitor(distance_threshold=150, time_threshold=10, takeover_confirm_frames=10)
out, t = run(m, [[owner(OWNER_NEAR), bag_at(40, BAG_CX, BAG_CY)] for _ in range(5)], 4000.0, 0.1)
out, t = run(m, walker_frames(40, 1, 6), t, 0.1)
check("passer-by partway through is counted", m.baggage_pool[40].retrieval_streaks.get(2) == 6,
      str(m.baggage_pool[40].retrieval_streaks))
out, t = run(m, [[bag_at(40, BAG_CX + 200, BAG_CY)]], t, 0.1)
check("pending takeover is cleared when nobody is near", m.baggage_pool[40].retrieval_streaks == {},
      str(m.baggage_pool[40].retrieval_streaks))
check("original owner still linked after brief passer-by", m.baggage_pool[40].owner_id == 1)

# --- 5. Alert re-arms for a new separation episode (O-2) ---
m = AdvancedBaggageMonitor(distance_threshold=150, time_threshold=10)
out, t = run(m, [[owner(OWNER_NEAR), bag_at(50, BAG_CX, BAG_CY)] for _ in range(5)], 5000.0, 0.1)

out, t = run(m, [[owner(OWNER_FAR), bag_at(50, BAG_CX, BAG_CY)] for _ in range(3)], t, 1.0)
out, t = run(m, [[owner(OWNER_FAR), bag_at(50, BAG_CX, BAG_CY)] for _ in range(12)], t, 1.0)
tel1 = telemetry_for(out, 50)
episode1 = tel1["episode"]
check("first separation raises alert", tel1["state"] == "UNATTENDED_ALERT", tel1["state"])

out, t = run(m, [[owner(OWNER_NEAR), bag_at(50, BAG_CX, BAG_CY)] for _ in range(5)], t, 0.1)
tel2 = telemetry_for(out, 50)
check("owner returns: bag no longer in alert", tel2["state"] in ("STATIC_ATTENDED", "CARRIED"), tel2["state"])

out, t = run(m, [[owner(OWNER_FAR), bag_at(50, BAG_CX, BAG_CY)] for _ in range(3)], t, 1.0)
out, t = run(m, [[owner(OWNER_FAR), bag_at(50, BAG_CX, BAG_CY)] for _ in range(12)], t, 1.0)
tel3 = telemetry_for(out, 50)
check("second separation raises alert again", tel3["state"] == "UNATTENDED_ALERT", tel3["state"])
check("second separation is a new episode", tel3["episode"] != episode1,
      f"episode {episode1} -> {tel3['episode']}")

# --- 6. One continuous separation keeps one episode number ---
m = AdvancedBaggageMonitor(distance_threshold=150, time_threshold=10)
out, t = run(m, [[owner(OWNER_NEAR), bag_at(60, BAG_CX, BAG_CY)] for _ in range(5)], 6000.0, 0.1)
out, t = run(m, [[owner(OWNER_FAR), bag_at(60, BAG_CX, BAG_CY)] for _ in range(3)], t, 1.0)
e_start = telemetry_for(out, 60)["episode"]
out, t = run(m, [[owner(OWNER_FAR), bag_at(60, BAG_CX, BAG_CY)] for _ in range(8)], t, 1.0)
e_later = telemetry_for(out, 60)["episode"]
check("one continuous separation keeps one episode number", e_start == e_later, f"{e_start} vs {e_later}")

passed = sum(results)
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
