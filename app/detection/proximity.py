import math


def euclidean_distance(p1, p2):
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def get_center(box):
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)
