PERSON_CLASS_ID = 0

SUPPORTED_CLASSES = {
    0: "person",
    24: "backpack",
    26: "handbag",
    28: "suitcase",
    63: "laptop",
}

# Objects that can be left behind. Laptops are opt-in: they are only tracked when
# monitored_classes includes them (see Settings → Objects to monitor).
BAG_CLASSES = ("backpack", "handbag", "suitcase", "laptop")

# Bags that YOLO often confuses with each other, so a track may switch between them.
# Laptops are not in this group: a laptop track only matches laptop detections.
CROSS_BAG_CLASSES = ("backpack", "handbag", "suitcase")
