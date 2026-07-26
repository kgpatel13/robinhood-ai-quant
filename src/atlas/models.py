from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

AssetClass = Literal["stock", "crypto"]
StrategyName = Literal["momentum_swing", "mean_reversion", "intraday_momentum", "cash"]


@dataclass(frozen=True)
class AtlasConfig:
    output_root: Path = Path("reports/atlas_v2")
    experiment_root: Path = Path("reports/atlas_v2/experiments")
    baseline_signoff: Path = Path(
        "reports/phase18_6_institutional_validation/phase18_final_signoff.json"
    )
    stock_universe_path: Path = Path("data/universe/stocks.csv")
    crypto_universe_path: Path = Path("data/universe/crypto.csv")
    universe_registry_path: Path = Path("data/universe/registry.json")
    universe_registry_csv_path: Path = Path("data/universe/registry.csv")
    universe_report_path: Path = Path("reports/atlas_v2/universe_update.json")
    nasdaq_listed_url: str = (
        "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
    )
    other_listed_url: str = (
        "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
    )
    coingecko_markets_url: str = "https://api.coingecko.com/api/v3/coins/markets"
    coingecko_api_key_env: str = "COINGECKO_DEMO_API_KEY"
    maximum_crypto_universe_assets: int = 250
    universe_request_timeout_seconds: float = 30.0
    market_history_root: Path = Path("data/market/daily")
    market_feature_store_path: Path = Path("data/market/features.csv")
    market_snapshot_path: Path = Path("reports/atlas_v2/market_snapshot.json")
    market_report_path: Path = Path("reports/atlas_v2/market_intelligence.json")
    history_report_path: Path = Path("reports/atlas_v2/history_download_report.json")
    history_stock_limit: int = 100
    history_crypto_limit: int = 50
    history_lookback_days: int = 730
    random_seed: int = 42
    top_candidates: int = 100
    minimum_price: float = 1.0
    minimum_daily_dollar_volume: float = 1_000_000.0
    maximum_stock_holding_days: int = 7
    maximum_crypto_holding_days: int = 7
    paper_trading_enabled: bool = False
    live_trading_enabled: bool = False


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    asset_class: AssetClass
    price: float
    average_daily_volume: float
    return_1d: float
    return_5d: float
    return_20d: float
    volatility_20d: float
    distance_from_20d_high: float
    relative_volume: float
    spread_bps: float


@dataclass(frozen=True)
class OpportunityScore:
    symbol: str
    asset_class: AssetClass
    alpha_score: float
    confidence: float
    regime: str
    strategy: StrategyName
    expected_holding_days: int
    components: dict[str, float] = field(default_factory=dict)
    explanation: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExperimentManifest:
    experiment_id: str
    created_at_utc: str
    platform_version: str
    git_commit: str
    git_dirty: bool
    random_seed: int
    config_sha256: str
    input_fingerprints: dict[str, str]
    baseline_fingerprint: str | None
    artifacts: dict[str, str]


@dataclass(frozen=True)
class AtlasRunResult:
    experiment_id: str
    scanned_assets: int
    eligible_assets: int
    ranked_assets: int
    top_strategy_counts: dict[str, int]
    diagnostics_passed: bool
    approved_for_paper_trading: bool
    approved_for_live_trading: bool
    output: str
    artifacts: dict[str, str] = field(default_factory=dict)
