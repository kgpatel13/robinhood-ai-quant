from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from src.atlas.ranking.core import (
    RankedAsset,
    RankingConfig,
    confidence_label,
    finite_score,
    percentile_positions,
)


@dataclass(frozen=True)
class RankingResult:
    ranked_assets: tuple[RankedAsset, ...]
    top_assets: tuple[RankedAsset, ...]
    bottom_assets: tuple[RankedAsset, ...]
    excluded_assets: tuple[str, ...]


class RankingEngine:
    def __init__(self, config: RankingConfig | None = None) -> None:
        self._config = config or RankingConfig()

    def rank(
        self,
        alpha_scores: Mapping[str, float | None],
        normalized_factors: Mapping[str, Mapping[str, float | None]],
        metadata_by_asset: Mapping[str, Mapping[str, str]],
    ) -> RankingResult:
        eligible: list[tuple[str, float]] = []
        excluded: list[str] = []
        for asset_id, value in alpha_scores.items():
            score = finite_score(value)
            if score is None:
                excluded.append(asset_id)
                continue
            if self._config.minimum_alpha is not None and score < self._config.minimum_alpha:
                excluded.append(asset_id)
                continue
            eligible.append((asset_id, score))

        ascending = sorted(eligible, key=lambda item: (item[1], item[0]))
        percentile_by_asset = {
            asset_id: percentile
            for (asset_id, _), percentile in zip(
                ascending,
                percentile_positions([score for _, score in ascending]),
                strict=True,
            )
        }
        descending = sorted(eligible, key=lambda item: (-item[1], item[0]))
        ranked: list[RankedAsset] = []
        for rank, (asset_id, score) in enumerate(descending, start=1):
            metadata = metadata_by_asset.get(asset_id, {})
            factors = normalized_factors.get(asset_id, {})
            percentile = percentile_by_asset[asset_id]
            ranked.append(
                RankedAsset(
                    rank=rank,
                    asset_id=asset_id,
                    symbol=metadata.get("symbol", asset_id),
                    asset_class=metadata.get("asset_class", "unknown"),
                    timestamp=metadata.get("timestamp", ""),
                    alpha_score=score,
                    alpha_percentile=percentile,
                    confidence=confidence_label(percentile, self._config),
                    factor_scores=dict(factors),
                    factor_coverage=sum(value is not None for value in factors.values()),
                )
            )

        bottom = tuple(reversed(ranked[-self._config.bottom_n :])) if self._config.bottom_n else ()
        return RankingResult(
            ranked_assets=tuple(ranked),
            top_assets=tuple(ranked[: self._config.top_n]),
            bottom_assets=bottom,
            excluded_assets=tuple(sorted(excluded)),
        )
