from pathlib import Path

import pytest

from src.control_center import ControlCenterProfile, ProfileStore, RiskLimits


def test_profile_is_always_paper_only() -> None:
    with pytest.raises(ValueError, match="paper-only"):
        ControlCenterProfile(paper_only=False)


def test_profile_round_trip(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path)
    original = ControlCenterProfile(name="Test Profile", risk=RiskLimits(maximum_open_positions=3))
    store.save(original)
    loaded = store.load("Test Profile")
    assert loaded == original
    assert store.list_profiles() == ("test_profile",)
