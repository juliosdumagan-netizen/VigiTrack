"""
Stationary-timer baseline: the naive comparison method for the evaluation.

Rule: if a bag has not moved more than `static_tolerance_px` for `time_threshold`
seconds, raise an alert — regardless of whether a person is standing next to it.
The alert clears when the object moves again.

This is deliberately ownership-blind. It is the "classic" motionless-object
detector the panel asked us to compare against: it should catch abandoned bags,
but it also fires on any bag that sits still beside its owner (seated readers).
"""

BAG_CLASSES = ("backpack", "handbag", "suitcase")


def _centroid(box):
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)


class StationaryTimerBaseline:
    """Alerts when a bag has been motionless for `time_threshold` seconds."""

    def __init__(self, time_threshold: float = 10.0, static_tolerance_px: float = 3.0):
        self.time_threshold = float(time_threshold)
        self.static_tolerance_px = float(static_tolerance_px)
        self._bags = {}  # bag id -> {"anchor", "anchor_time", "alerting"}

    def update(self, detections, now: float):
        """Returns per-bag telemetry in the same shape the evaluator uses for the FSM."""
        telemetry = []
        for det in detections:
            if det["class_name"] not in BAG_CLASSES:
                continue
            bag_id = det["id"]
            centre = _centroid(det["box"])
            state = self._bags.get(bag_id)

            if state is None:
                state = {"anchor": centre, "anchor_time": float(now), "alerting": False}
                self._bags[bag_id] = state
            elif ((centre[0] - state["anchor"][0]) ** 2 + (centre[1] - state["anchor"][1]) ** 2) ** 0.5 > self.static_tolerance_px:
                state["anchor"] = centre
                state["anchor_time"] = float(now)
                state["alerting"] = False

            if not state["alerting"] and (float(now) - state["anchor_time"]) >= self.time_threshold:
                state["alerting"] = True

            telemetry.append({
                "bag_id": bag_id,
                "class_name": det["class_name"],
                "box": det["box"],
                "static_for": float(now) - state["anchor_time"],
                "is_alert": state["alerting"],
            })
        return telemetry
