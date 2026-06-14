# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class TickerMeta:
    ticker: str
    market: str
    themes: tuple[str, ...]
    theme_score: float


def _dedupe(seq: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in seq:
        if not x:
            continue
        x = str(x).strip().upper()
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


def build_universe(raw: dict, market: str = "all") -> dict[str, TickerMeta]:
    universe_raw = raw.get("universe", {}) or {}
    weights = raw.get("theme_weights", {}) or {}
    markets = ["US", "TW"] if market.lower() == "all" else [market.upper()]

    result: dict[str, dict] = {}
    for mkt in markets:
        by_theme = universe_raw.get(mkt, {}) or {}
        for theme, tickers in by_theme.items():
            for ticker in _dedupe(tickers):
                if ticker not in result:
                    result[ticker] = {"market": mkt, "themes": set(), "theme_score": 0.0}
                result[ticker]["themes"].add(theme)
                result[ticker]["theme_score"] += float(weights.get(theme, 1.0))

    metas: dict[str, TickerMeta] = {}
    for ticker, data in result.items():
        themes = tuple(sorted(data["themes"]))
        metas[ticker] = TickerMeta(
            ticker=ticker,
            market=data["market"],
            themes=themes,
            theme_score=round(float(data["theme_score"]), 2),
        )
    return metas


def tickers_by_market(universe: dict[str, TickerMeta], market: str) -> list[str]:
    return [t for t, meta in universe.items() if meta.market == market.upper()]
