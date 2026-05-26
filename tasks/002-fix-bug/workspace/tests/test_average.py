import pytest

from stats.average import weighted_average


def test_equal_weights_match_arithmetic_mean():
    assert weighted_average([1, 2, 3, 4], [1, 1, 1, 1]) == pytest.approx(2.5)


def test_basic_weighted():
    # (1*3 + 2*7) / (3 + 7) = 17 / 10 = 1.7
    assert weighted_average([1, 2], [3, 7]) == pytest.approx(1.7)


def test_uneven_weights():
    # (10*1 + 20*4) / (1 + 4) = 90 / 5 = 18.0
    assert weighted_average([10, 20], [1, 4]) == pytest.approx(18.0)


def test_zero_weight_is_ignored():
    # weight 0 means the value should not contribute
    assert weighted_average([5, 100], [1, 0]) == pytest.approx(5.0)


def test_length_mismatch_raises():
    with pytest.raises(ValueError):
        weighted_average([1, 2, 3], [1, 1])


def test_negative_weight_raises():
    with pytest.raises(ValueError):
        weighted_average([1, 2], [1, -1])


def test_empty_raises():
    with pytest.raises(ValueError):
        weighted_average([], [])


def test_all_zero_weights_raises():
    with pytest.raises(ValueError):
        weighted_average([1, 2, 3], [0, 0, 0])
