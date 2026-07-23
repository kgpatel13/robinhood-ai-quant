from src.data.demo import make_demo_bars
from src.data.quality import DataQualityValidator


def test_valid_bars_pass() -> None:
    report = DataQualityValidator().validate(make_demo_bars(rows=5))
    assert report.passed
    assert report.rows == 5


def test_duplicate_bars_fail() -> None:
    frame = make_demo_bars(rows=3)
    frame.loc[1, "timestamp"] = frame.loc[0, "timestamp"]
    report = DataQualityValidator().validate(frame)
    assert not report.passed
    assert any(issue.code == "duplicate_bars" for issue in report.issues)


def test_invalid_ohlc_fails() -> None:
    frame = make_demo_bars(rows=3)
    frame.loc[0, "high"] = frame.loc[0, "low"] - 1
    report = DataQualityValidator().validate(frame)
    assert not report.passed
    assert any(issue.code == "invalid_ohlc" for issue in report.issues)
