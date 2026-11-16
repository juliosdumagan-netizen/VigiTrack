PERSON_CLASS_ID = 0

SUPPORTED_CLASSES = {
    0: "person",
    24: "backpack",
    26: "handbag",
    28: "suitcase",
    63: "laptop",
    67: "cell phone",
}

# Objects that can be left behind. Laptops and cell phones are opt-in: they are only tracked
# when monitored_classes includes them (see Settings → Objects to monitor).
BAG_CLASSES = ("backpack", "handbag", "suitcase", "laptop", "cell phone")

# Bags that YOLO often confuses with each other, so a track may switch between them.
# Laptops and cell phones are excluded: their tracks only match their own class.
CROSS_BAG_CLASSES = ("backpack", "handbag", "suitcase")
