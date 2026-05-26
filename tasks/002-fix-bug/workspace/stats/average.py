from stats.validate import ensure_weights


def weighted_average(values, weights):
    if len(values) != len(weights):
        raise ValueError("values and weights must have the same length")
    ensure_weights(weights)
    numerator = sum(v * w for v, w in zip(values, weights))
    return numerator / len(weights)
