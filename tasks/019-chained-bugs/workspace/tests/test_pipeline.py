"""End-to-end tests for the ETL pipeline.

Layout
------
- TestExtract : exercises extract.extract_csv directly on a CSV fixture.
- TestTransform : exercises transform.aggregate on records produced by
  extract (so the fixture itself depends on extract working).
- TestLoad : exercises load.load_to_store on aggregates produced by the
  full pipeline (extract -> transform -> load).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from etl.extract import extract_csv
from etl.transform import aggregate
from etl.load import load_to_store


# Path to the bundled fixture CSV. The CSV lives next to the etl/ package
# under data/, and the working directory when pytest runs is workspace/.
DATA = Path(__file__).resolve().parent.parent / "data" / "sample.csv"


# ---------------------------------------------------------------------------
# Fixtures
#
# All non-trivial assertions flow through these fixtures, so a failure in
# an upstream step (extract -> transform -> load) shows up as a fixture
# ERROR in pytest's report, not as a FAILURE in a downstream test. This
# keeps each layer's bugs from leaking into the symptom of a deeper layer.


@pytest.fixture
def records():
    """Records as produced by extract_csv on the sample CSV."""
    return extract_csv(DATA)


@pytest.fixture
def aggregates(records):
    """Aggregates as produced by transform.aggregate."""
    return aggregate(records)


# ---------------------------------------------------------------------------
# Extract


class TestExtract:
    def test_extract_returns_a_list_of_dicts(self):
        out = extract_csv(DATA)
        assert isinstance(out, list)
        assert all(isinstance(r, dict) for r in out)

    def test_extract_row_count(self):
        # The fixture CSV has 9 data rows (header excluded).
        out = extract_csv(DATA)
        assert len(out) == 9

    def test_extract_record_shape(self):
        out = extract_csv(DATA)
        first = out[0]
        assert set(first.keys()) == {"category", "name", "value"}

    def test_extract_typed_value(self):
        out = extract_csv(DATA)
        # First fruit row: apple, value 10
        apple = next(r for r in out if r["name"] == "apple")
        assert apple["value"] == 10
        assert isinstance(apple["value"], int)

    def test_extract_empty_value_becomes_none(self):
        out = extract_csv(DATA)
        # eggplant has an empty value cell in the fixture
        eggplant = next(r for r in out if r["name"] == "eggplant")
        assert eggplant["value"] is None


# ---------------------------------------------------------------------------
# Transform
#
# These tests use the `records` fixture, which depends on extract working.
# As long as extract is broken, these report as ERRORs (fixture failure),
# not FAILUREs. Once extract is fixed, the real assertions run and the
# transform-level bug surfaces.


class TestTransform:
    def test_transform_groups_by_category(self, records):
        out = aggregate(records)
        assert set(out.keys()) == {"fruit", "veggie", "grain", "solo"}

    def test_transform_counts_non_null_values(self, records):
        out = aggregate(records)
        # fruit: 3 values, veggie: 2 (eggplant is None), grain: 2, solo: 1
        assert out["fruit"]["count"] == 3
        assert out["veggie"]["count"] == 2
        assert out["grain"]["count"] == 2
        assert out["solo"]["count"] == 1

    def test_transform_totals(self, records):
        out = aggregate(records)
        assert out["fruit"]["total"] == 60   # 10 + 20 + 30
        assert out["veggie"]["total"] == 20  # 5 + 15
        assert out["grain"]["total"] == 100  # 40 + 60
        assert out["solo"]["total"] == 7

    def test_transform_average_is_arithmetic_mean(self, records):
        out = aggregate(records)
        assert out["fruit"]["average"] == pytest.approx(20.0)   # 60 / 3
        assert out["veggie"]["average"] == pytest.approx(10.0)  # 20 / 2
        assert out["grain"]["average"] == pytest.approx(50.0)   # 100 / 2

    def test_transform_handles_single_element_category(self, records):
        # The "solo" category has exactly one value (7). The average must
        # equal that value — not 0, not a division-by-zero error.
        out = aggregate(records)
        assert out["solo"]["average"] == pytest.approx(7.0)


# ---------------------------------------------------------------------------
# Load
#
# These tests use the `aggregates` fixture, which depends on both extract
# AND transform working (no exception). As long as either upstream step is
# broken, these report as ERRORs. Once both are fixed, the load-level bug
# (duplicate inserts) surfaces.


class TestLoad:
    def test_load_appends_one_row_per_category(self, aggregates):
        store: list[dict] = []
        added = load_to_store(aggregates, store)
        # 4 categories -> exactly 4 rows in the store.
        assert added == 4
        assert len(store) == 4

    def test_load_preserves_aggregate_values(self, aggregates):
        store: list[dict] = []
        load_to_store(aggregates, store)
        # Group rows by category. With no duplicates, every category
        # appears exactly once.
        by_cat: dict[str, list[dict]] = {}
        for row in store:
            by_cat.setdefault(row["category"], []).append(row)
        assert set(by_cat.keys()) == {"fruit", "veggie", "grain", "solo"}
        for cat, rows in by_cat.items():
            assert len(rows) == 1, f"category {cat!r} appears {len(rows)} times"
        assert by_cat["fruit"][0]["total"] == 60
        assert by_cat["fruit"][0]["count"] == 3
        assert by_cat["fruit"][0]["average"] == pytest.approx(20.0)

    def test_load_is_idempotent_per_call(self, aggregates):
        # Calling load_to_store once must add exactly len(aggregates) rows
        # — not double-write, not skip.
        store: list[dict] = []
        n1 = load_to_store(aggregates, store)
        assert len(store) == n1
        n2 = load_to_store(aggregates, store)
        assert len(store) == n1 + n2
