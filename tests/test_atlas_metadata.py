from __future__ import annotations

from pathlib import Path

from src.atlas.portfolio.metadata import (
    AssetMetadata,
    enrich_metadata,
    read_metadata,
    write_metadata,
)


class FakeProvider:
    def fetch(self, symbol: str) -> dict[str, object]:
        assert symbol == "AAA"
        return {
            "sector": "Technology",
            "industry": "Software",
            "country": "United States",
            "marketCap": 1_500_000_000,
        }


def test_metadata_enrichment_supports_stocks_and_crypto(tmp_path: Path) -> None:
    records = enrich_metadata(
        [
            ("stock:AAA", "AAA", "stock"),
            ("crypto:bitcoin", "BTC", "crypto"),
        ],
        provider=FakeProvider(),
    )
    assert records["stock:AAA"].status == "complete"
    assert records["stock:AAA"].sector == "Technology"
    assert records["crypto:bitcoin"].sector == "Digital Assets"
    assert records["crypto:bitcoin"].country == "Global"

    output = tmp_path / "metadata.csv"
    write_metadata(output, records.values())
    loaded = read_metadata(output)
    assert loaded == records


def test_metadata_enrichment_resumes_existing_records() -> None:
    existing = AssetMetadata(
        asset_id="stock:AAA",
        symbol="AAA",
        asset_class="stock",
        sector="Technology",
        industry="Software",
        country="United States",
        market_cap=1.0,
        source="test",
        status="complete",
    )

    class FailingProvider:
        def fetch(self, symbol: str) -> dict[str, object]:
            raise AssertionError("provider should not be called")

    result = enrich_metadata(
        [("stock:AAA", "AAA", "stock")],
        existing={existing.asset_id: existing},
        provider=FailingProvider(),
    )
    assert result[existing.asset_id] == existing
