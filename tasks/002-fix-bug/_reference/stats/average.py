from stats.validate import ensure_weights


def weighted_average(values, weights):
    if len(values) != len(weights):
        raise ValueError("values and weights must have the same length")
    ensure_weights(weights)
    total_weight = sum(weights)
    if total_weight == 0:
        raise ValueError("weights sum to zero")
    numerator = sum(v * w for v, w in zip(values, weights))
    return numerator / total_weight
