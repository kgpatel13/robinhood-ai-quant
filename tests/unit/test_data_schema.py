from src.data.demo import make_demo_bars
from src.data.schema import BAR_COLUMNS


def test_demo_uses_normalized_schema() -> None:
    frame = make_demo_bars(rows=3)
    assert tuple(frame.columns) == BAR_COLUMNS
    assert str(frame["timestamp"].dt.tz) == "UTC"
