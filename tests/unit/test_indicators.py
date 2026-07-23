import pandas as pd
import pytest

from src.strategies.indicators import atr, bollinger_bands, ema, macd, rsi, sma, vwap


def test_indicator_shapes_and_values() -> None:
    values = pd.Series(range(1, 41), dtype=float)
    assert sma(values, 5).iloc[-1] == pytest.approx(38.0)
    assert ema(values, 5).notna().sum() == 36
    assert rsi(values, 14).iloc[-1] == pytest.approx(100.0)
    assert list(macd(values).columns) == ["macd", "signal", "histogram"]
    assert list(bollinger_bands(values).columns) == ["lower", "middle", "upper"]


def test_bar_indicators() -> None:
    bars = pd.DataFrame(
        {
            "high": [11.0, 12.0, 13.0],
            "low": [9.0, 10.0, 11.0],
            "close": [10.0, 11.0, 12.0],
            "volume": [100.0, 100.0, 100.0],
        }
    )
    assert atr(bars, 2).iloc[-1] == pytest.approx(2.0)
    assert vwap(bars).iloc[-1] == pytest.approx(11.0)
