from src.data.demo import make_demo_bars
from src.data.storage import ParquetBarStore


def test_parquet_round_trip(tmp_path) -> None:
    store = ParquetBarStore(tmp_path)
    path = store.write(make_demo_bars("SPY", rows=3), "stock", "SPY")
    assert path.exists()
    assert path.with_suffix(".manifest.json").exists()
    loaded = store.read("stock", "SPY")
    assert len(loaded) == 3


def test_store_upserts_duplicate_dates(tmp_path) -> None:
    store = ParquetBarStore(tmp_path)
    frame = make_demo_bars("SPY", rows=3)
    store.write(frame, "stock", "SPY")
    store.write(frame, "stock", "SPY")
    assert len(store.read("stock", "SPY")) == 3
