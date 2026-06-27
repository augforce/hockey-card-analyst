"""Tests for the percentile -> tier logic (PLAN section 5)."""
import pytest

from engine.tiers import Tier, classify_percentile

# (percentile, expected label) at the interior and both edges of every band.
BAND_CASES = [
    # Elite: 95-100
    (95, "Elite"),
    (99, "Elite"),
    (100, "Elite"),
    # Excellent: 85-94
    (85, "Excellent"),
    (90, "Excellent"),
    (94, "Excellent"),
    # Strong: 70-84
    (70, "Strong"),
    (84, "Strong"),
    # Above average: 55-69
    (55, "Above average"),
    (69, "Above average"),
    # Average: 45-54
    (45, "Average"),
    (50, "Average"),
    (54, "Average"),
    # Below average: 30-44
    (30, "Below average"),
    (44, "Below average"),
    # Weak: 15-29
    (15, "Weak"),
    (29, "Weak"),
    # Among the worst: 0-14
    (0, "Among the worst at the position"),
    (14, "Among the worst at the position"),
]


@pytest.mark.parametrize("percentile,label", BAND_CASES)
def test_label_for_each_band_and_boundary(percentile, label):
    assert classify_percentile(percentile).label == label


def test_returns_tier_with_band_bounds():
    elite = classify_percentile(99)
    assert isinstance(elite, Tier)
    assert elite.percentile == 99
    assert elite.band == (95, 100)

    average = classify_percentile(50)
    assert average.band == (45, 54)


@pytest.mark.parametrize("percentile", [95, 99, 100])
def test_elite_compression_note_attached_at_or_above_95(percentile):
    tier = classify_percentile(percentile)
    assert tier.note is not None
    assert tier.note.strip() != ""


@pytest.mark.parametrize("percentile", [0, 50, 84, 94])
def test_no_compression_note_below_95(percentile):
    assert classify_percentile(percentile).note is None


@pytest.mark.parametrize("bad", [-1, 101, 200, -50])
def test_out_of_range_raises_value_error(bad):
    with pytest.raises(ValueError):
        classify_percentile(bad)


@pytest.mark.parametrize("bad", [True, False])
def test_bool_is_rejected(bad):
    # bool is a subclass of int; a stray True/False must not be read as 1/0.
    with pytest.raises(TypeError):
        classify_percentile(bad)


def test_bands_are_driven_by_config():
    # A custom config proves cutoffs/labels/notes are not hard-coded.
    custom = {
        "tiers": [
            {"min": 0, "max": 49, "label": "Low"},
            {"min": 50, "max": 100, "label": "High"},
        ],
        "elite_compression": {"threshold": 50, "note": "top half"},
    }
    high = classify_percentile(60, config=custom)
    assert high.label == "High"
    assert high.band == (50, 100)
    assert high.note == "top half"

    low = classify_percentile(10, config=custom)
    assert low.label == "Low"
    assert low.note is None
