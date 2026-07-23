from datetime import date
from unittest.mock import Mock, patch

from src.data.providers.coingecko import CoinGeckoProvider


def test_coingecko_normalizes_intraday_points_to_daily_bars() -> None:
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "prices": [[1735689600000, 100.0], [1735732800000, 110.0], [1735776000000, 105.0]],
        "total_volumes": [[1735689600000, 1000.0], [1735732800000, 1200.0], [1735776000000, 900.0]],
    }
    provider = CoinGeckoProvider({"BTC-USD": "bitcoin"}, api_key="unit-test-key")
    with patch("src.data.providers.coingecko.requests.get", return_value=response):
        frame = provider.fetch_daily_bars("BTC-USD", "crypto", date(2025, 1, 1), date(2025, 1, 2))
    assert len(frame) == 2
    assert frame.iloc[0]["high"] == 110.0
    assert frame.iloc[0]["close"] == 110.0
