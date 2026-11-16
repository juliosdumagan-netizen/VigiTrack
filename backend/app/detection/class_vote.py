"""
Per-track class voting.

The detector labels each frame on its own, so an object can flip between
handbag, backpack and suitcase from one frame to the next. A track keeps the
labels it has seen over a short window, and its class is the most common one.
The counts and best confidence per class are kept as evidence, so a reviewer
can see when the model was unsure.
"""

from collections import Counter, deque
from typing import Any, Dict, Iterable, Optional

HISTORY_FRAMES = 21


class ClassHistory:
    """The recent (class, confidence) observations for one track."""

    def __init__(self, maxlen: int = HISTORY_FRAMES):
        self._items: deque = deque(maxlen=maxlen)

    def add(self, class_name: str, confidence: float) -> None:
        self._items.append((class_name, float(confidence)))

    def dominant(self) -> Optional[str]:
        """The most common class in the window. A tie goes to the most recent of the tied classes."""
        if not self._items:
            return None
        counts = Counter(name for name, _ in self._items)
        best = max(counts.values())
        for name, _ in reversed(self._items):
            if counts[name] == best:
                return name
        return None

    def evidence(self) -> Dict[str, Dict[str, float]]:
        """Frames seen and best confidence for each class in the window."""
        out: Dict[str, Dict[str, float]] = {}
        for name, conf in self._items:
            entry = out.setdefault(name, {"frames": 0, "max_confidence": 0.0})
            entry["frames"] += 1
            entry["max_confidence"] = max(entry["max_confidence"], round(conf, 3))
        return out


def class_stability(labels: Iterable[str]) -> Dict[str, Any]:
    """
    How consistent one track's per-frame labels are. Used to measure the labelling
    problem on recorded clips before deciding whether to retrain.
    """
    counts = Counter(labels)
    total = sum(counts.values())
    if total == 0:
        return {"frames": 0, "dominant": None, "agreement": None, "counts": {}}
    dominant, top = counts.most_common(1)[0]
    return {
        "frames": total,
        "dominant": dominant,
        "agreement": top / total,
        "counts": dict(counts),
    }
