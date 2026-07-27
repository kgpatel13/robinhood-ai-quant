from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence

from src.atlas.portfolio.core import (
    CurrentPosition,
    PortfolioCandidate,
    PortfolioConfig,
    PortfolioDiagnostics,
    PortfolioMetrics,
    PortfolioResult,
    RebalanceAction,
    TargetPosition,
    confidence_rank,
    normalize_weights,
)


def _raw_weight(candidate: PortfolioCandidate, method: str, fallback_volatility: float) -> float:
    score = max(candidate.alpha_percentile, 0.01)
    volatility = candidate.volatility_60d or fallback_volatility
    inverse_volatility = 1.0 / max(volatility, 0.05)
    if method == "equal":
        return 1.0
    if method == "score":
        return score
    if method == "volatility":
        return inverse_volatility
    return math.sqrt(score * inverse_volatility)


def _cap_and_redistribute(
    weights: list[float],
    candidates: Sequence[PortfolioCandidate],
    config: PortfolioConfig,
    investable_weight: float,
) -> list[float]:
    result = [0.0] * len(weights)
    remaining = investable_weight
    active = set(range(len(weights)))
    raw = list(weights)
    while active and remaining > 1e-12:
        denominator = sum(raw[index] for index in active)
        proposed = (
            {index: remaining / len(active) for index in active}
            if denominator <= 0
            else {index: remaining * raw[index] / denominator for index in active}
        )
        capped: set[int] = set()
        for index, value in proposed.items():
            cap = config.max_position_pct
            if candidates[index].asset_class.lower() == "crypto":
                cap = min(cap, config.max_crypto_pct)
            if value > cap + 1e-12:
                result[index] = cap
                remaining -= cap
                capped.add(index)
        if not capped:
            for index, value in proposed.items():
                result[index] = value
            remaining = 0.0
        active -= capped
    return result


def _apply_group_limit(
    weights: list[float],
    candidates: Sequence[PortfolioCandidate],
    attribute: str,
    limit: float,
    config: PortfolioConfig,
) -> list[float]:
    adjusted = list(weights)
    groups: dict[str, list[int]] = defaultdict(list)
    for index, candidate in enumerate(candidates):
        value = getattr(candidate, attribute)
        if value:
            groups[str(value).strip().lower()].append(index)
    for indexes in groups.values():
        group_total = sum(adjusted[index] for index in indexes)
        if group_total <= limit + 1e-12:
            continue
        scale = limit / group_total
        freed = 0.0
        for index in indexes:
            new_weight = adjusted[index] * scale
            freed += adjusted[index] - new_weight
            adjusted[index] = new_weight
        recipients = [index for index in range(len(candidates)) if index not in indexes]
        capacity = [max(config.max_position_pct - adjusted[index], 0.0) for index in recipients]
        total_capacity = sum(capacity)
        if freed > 0 and total_capacity > 0:
            for index, room in zip(recipients, capacity, strict=True):
                adjusted[index] += min(freed * room / total_capacity, room)
    return adjusted


def _apply_crypto_limit(
    weights: list[float], candidates: Sequence[PortfolioCandidate], config: PortfolioConfig
) -> list[float]:
    crypto_indexes = [
        index for index, candidate in enumerate(candidates)
        if candidate.asset_class.lower() == "crypto"
    ]
    crypto_total = sum(weights[index] for index in crypto_indexes)
    if crypto_total <= config.max_crypto_pct + 1e-12:
        return weights
    scale = config.max_crypto_pct / crypto_total if crypto_total else 0.0
    adjusted = list(weights)
    freed = 0.0
    for index in crypto_indexes:
        new_weight = adjusted[index] * scale
        freed += adjusted[index] - new_weight
        adjusted[index] = new_weight
    stock_indexes = [index for index in range(len(candidates)) if index not in crypto_indexes]
    available = [max(config.max_position_pct - adjusted[index], 0.0) for index in stock_indexes]
    capacity = sum(available)
    if capacity > 0 and freed > 0:
        for index, room in zip(stock_indexes, available, strict=True):
            adjusted[index] += min(freed * room / capacity, room)
    return adjusted


def _round_quantity(
    candidate: PortfolioCandidate,
    value: float,
    config: PortfolioConfig,
) -> float | None:
    if candidate.price is None or candidate.price <= 0:
        return None
    raw = value / candidate.price
    if candidate.asset_class.lower() == "crypto":
        return round(raw, config.crypto_share_precision)
    if not config.fractional_shares:
        return float(math.floor(raw))
    return round(raw, config.stock_share_precision)


class PortfolioEngine:
    def __init__(self, config: PortfolioConfig | None = None) -> None:
        self.config = config or PortfolioConfig()

    def construct(
        self,
        candidates: Sequence[PortfolioCandidate],
        current_positions: Sequence[CurrentPosition] = (),
    ) -> PortfolioResult:
        excluded: dict[str, str] = {}
        eligible: list[PortfolioCandidate] = []
        minimum_confidence = confidence_rank(self.config.minimum_confidence)
        for candidate in sorted(candidates, key=lambda item: (item.rank, item.asset_id)):
            if not candidate.asset_id or not candidate.symbol.strip():
                excluded[candidate.asset_id or f"invalid:{candidate.rank}"] = "invalid_identity"
                continue
            if candidate.asset_class.lower() not in {"stock", "crypto"}:
                excluded[candidate.asset_id] = "unsupported_asset_class"
                continue
            if candidate.alpha_percentile < self.config.minimum_alpha_percentile:
                excluded[candidate.asset_id] = "below_minimum_alpha_percentile"
                continue
            if confidence_rank(candidate.confidence) < minimum_confidence:
                excluded[candidate.asset_id] = "below_minimum_confidence"
                continue
            if len(eligible) >= self.config.max_positions:
                excluded[candidate.asset_id] = "outside_position_limit"
                continue
            eligible.append(candidate)

        vol_values = [
            item.volatility_60d
            for item in eligible
            if item.volatility_60d and item.volatility_60d > 0
        ]
        volatility_coverage = len(vol_values) / len(eligible) if eligible else 0.0
        price_coverage = (
            sum(bool(item.price and item.price > 0) for item in eligible) / len(eligible)
            if eligible
            else 0.0
        )
        sector_coverage = (
            sum(bool(item.sector) for item in eligible) / len(eligible)
            if eligible
            else 0.0
        )
        industry_coverage = (
            sum(bool(item.industry) for item in eligible) / len(eligible)
            if eligible
            else 0.0
        )

        effective_method = self.config.sizing_method
        fallback_reason: str | None = None
        if effective_method in {"volatility", "hybrid"} and not vol_values:
            effective_method = "score"
            fallback_reason = "volatility_unavailable"
        fallback_volatility = sorted(vol_values)[len(vol_values) // 2] if vol_values else 1.0

        investable_weight = 1.0 - self.config.cash_reserve_pct
        raw = [
            _raw_weight(candidate, effective_method, fallback_volatility)
            for candidate in eligible
        ]
        weights = _cap_and_redistribute(
            normalize_weights(raw, investable_weight), eligible, self.config, investable_weight
        )
        weights = _apply_crypto_limit(weights, eligible, self.config)
        if sector_coverage > 0:
            weights = _apply_group_limit(
                weights,
                eligible,
                "sector",
                self.config.max_sector_pct,
                self.config,
            )
        if industry_coverage > 0:
            weights = _apply_group_limit(
                weights,
                eligible,
                "industry",
                self.config.max_industry_pct,
                self.config,
            )
        weights = normalize_weights(weights, investable_weight)

        targets = tuple(
            TargetPosition(
                asset_id=candidate.asset_id,
                symbol=candidate.symbol,
                asset_class=candidate.asset_class,
                rank=candidate.rank,
                alpha_score=candidate.alpha_score,
                confidence=candidate.confidence,
                target_weight=weight,
                target_value=weight * self.config.capital,
                estimated_shares=_round_quantity(
                    candidate,
                    weight * self.config.capital,
                    self.config,
                ),
                price=candidate.price,
                sector=candidate.sector,
                industry=candidate.industry,
                country=candidate.country,
            )
            for candidate, weight in zip(eligible, weights, strict=True)
        )
        price_by_asset = {candidate.asset_id: candidate.price for candidate in eligible}
        actions = self._rebalance(targets, current_positions, price_by_asset)
        metrics = self._metrics(targets, actions, eligible, volatility_coverage, price_coverage)
        warnings: list[str] = []
        if fallback_reason:
            warnings.append("Requested volatility-aware sizing fell back to score weighting.")
        elif volatility_coverage < 1.0 and effective_method in {"volatility", "hybrid"}:
            warnings.append(
                "Missing volatility values were replaced with the eligible-universe median."
            )
        if price_coverage < 1.0:
            warnings.append(
                "Some order quantities are unavailable because latest prices are missing."
            )
        if sector_coverage == 0:
            warnings.append(
                "Sector limits were not applied because sector metadata is unavailable."
            )
        if industry_coverage == 0:
            warnings.append(
                "Industry limits were not applied because industry metadata is unavailable."
            )
        diagnostics = PortfolioDiagnostics(
            requested_sizing_method=self.config.sizing_method,
            effective_sizing_method=effective_method,
            sizing_fallback_reason=fallback_reason,
            volatility_coverage=volatility_coverage,
            price_coverage=price_coverage,
            sector_coverage=sector_coverage,
            industry_coverage=industry_coverage,
            warnings=tuple(warnings),
        )
        return PortfolioResult(
            targets=targets,
            actions=actions,
            metrics=metrics,
            diagnostics=diagnostics,
            excluded=excluded,
        )

    def _rebalance(
        self,
        targets: Sequence[TargetPosition],
        current_positions: Sequence[CurrentPosition],
        price_by_asset: Mapping[str, float | None],
    ) -> tuple[RebalanceAction, ...]:
        target_by_asset = {position.asset_id: position for position in targets}
        current_by_asset = {position.asset_id: position for position in current_positions}
        actions: list[RebalanceAction] = []
        for asset_id in sorted(set(target_by_asset) | set(current_by_asset)):
            target = target_by_asset.get(asset_id)
            current = current_by_asset.get(asset_id)
            current_value = current.market_value if current else 0.0
            target_value = target.target_value if target else 0.0
            difference = target_value - current_value
            threshold = self.config.rebalance_threshold_pct * self.config.capital
            if target is None:
                action = "SELL"
            elif current is None and target_value > threshold:
                action = "BUY"
            elif abs(difference) <= threshold:
                action = "HOLD"
            elif difference > 0:
                action = "BUY"
            else:
                action = "TRIM"
            if target is not None:
                symbol, asset_class = target.symbol, target.asset_class
            elif current is not None:
                symbol, asset_class = current.symbol, current.asset_class
            else:
                raise RuntimeError(f"Missing target and current position for {asset_id}")
            price = price_by_asset.get(asset_id)
            quantity = difference / price if price and price > 0 else None
            actions.append(
                RebalanceAction(
                    asset_id=asset_id,
                    symbol=symbol,
                    asset_class=asset_class,
                    action=action,
                    current_value=current_value,
                    target_value=target_value,
                    trade_value=difference,
                    current_weight=current_value / self.config.capital,
                    target_weight=target_value / self.config.capital,
                    estimated_shares=quantity,
                    price=price,
                    quantity_status="available" if quantity is not None else "latest_price_missing",
                )
            )
        return tuple(actions)

    def _metrics(
        self,
        targets: Sequence[TargetPosition],
        actions: Sequence[RebalanceAction],
        candidates: Sequence[PortfolioCandidate],
        volatility_coverage: float,
        price_coverage: float,
    ) -> PortfolioMetrics:
        invested_weight = sum(position.target_weight for position in targets)
        cash_weight = max(1.0 - invested_weight, 0.0)
        normalized = (
            [position.target_weight / invested_weight for position in targets]
            if invested_weight
            else []
        )
        hhi = sum(weight**2 for weight in normalized)
        crypto_weight = sum(
            position.target_weight for position in targets
            if position.asset_class.lower() == "crypto"
        )
        volatility_by_asset = {
            candidate.asset_id: candidate.volatility_60d for candidate in candidates
        }
        volatility_terms = [
            (position.target_weight * volatility) ** 2
            for position in targets
            if (
                volatility := volatility_by_asset.get(position.asset_id)
            ) is not None
            and volatility >= 0
        ]
        estimated_volatility = math.sqrt(sum(volatility_terms)) if volatility_terms else None
        turnover = sum(abs(action.trade_value) for action in actions) / (2 * self.config.capital)
        return PortfolioMetrics(
            invested_value=invested_weight * self.config.capital,
            cash_value=cash_weight * self.config.capital,
            cash_weight=cash_weight,
            position_count=len(targets),
            largest_position_weight=max((item.target_weight for item in targets), default=0.0),
            crypto_weight=crypto_weight,
            concentration_hhi=hhi,
            effective_positions=1.0 / hhi if hhi > 0 else 0.0,
            estimated_volatility=estimated_volatility,
            turnover=turnover,
            volatility_coverage=volatility_coverage,
            price_coverage=price_coverage,
        )
