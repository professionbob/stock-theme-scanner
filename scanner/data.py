# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
import time

import pandas as pd
import requests
import yfinance as yf


@dataclass
class QuoteBundle:
    ticker: str
    hist: pd.DataFrame
    info: dict[str, Any]
    news: list[dict[str, Any]]


def _normalize_download(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if df.empty:
        return df
    # yfinance 多檔下載會產生 multi-index columns。
    if isinstance(df.columns, pd.MultiIndex):
        if ticker in df.columns.get_level_values(0):
            df = df[ticker].copy()
        elif ticker in df.columns.get_level_values(1):
            df = df.xs(ticker, axis=1, level=1).copy()
    df = df.dropna(how="all")
    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        return pd.DataFrame()
    return df[required].dropna(subset=["Close"])


def download_history(tickers: list[str], period: str = "1y", interval: str = "1d") -> dict[str, pd.DataFrame]:
    if not tickers:
        return {}
    # 分批避免 Yahoo 限流或 URL 過長。
    result: dict[str, pd.DataFrame] = {}
    batch_size = 50
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i : i + batch_size]
        try:
            raw = yf.download(
                tickers=batch,
                period=period,
                interval=interval,
                group_by="ticker",
                auto_adjust=True,
                threads=True,
                progress=False,
            )
        except Exception as exc:
            print(f"下載行情失敗 batch={batch[:3]}... err={exc}")
            continue
        for ticker in batch:
            hist = _normalize_download(raw, ticker)
            if not hist.empty and len(hist) >= 60:
                result[ticker] = hist
        time.sleep(0.5)
    return result


def get_fast_info(ticker: str) -> dict[str, Any]:
    try:
        t = yf.Ticker(ticker)
        fast = dict(t.fast_info or {})
    except Exception:
        fast = {}
    return fast


def get_info(ticker: str) -> dict[str, Any]:
    try:
        t = yf.Ticker(ticker)
        info = t.get_info() or {}
    except Exception:
        info = {}
    return info


def get_news_yf(ticker: str, limit: int = 8) -> list[dict[str, Any]]:
    try:
        t = yf.Ticker(ticker)
        news = t.news or []
        return news[:limit]
    except Exception:
        return []


def get_finnhub_company_news(ticker: str, api_key: str | None, days: int = 14) -> list[dict[str, Any]]:
    if not api_key:
        return []
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    url = "https://finnhub.io/api/v1/company-news"
    params = {"symbol": ticker, "from": str(start), "to": str(end), "token": api_key}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json()[:10]
    except Exception:
        return []


def fetch_market_snapshot() -> dict[str, dict[str, Any]]:
    symbols = {
        "S&P500": "^GSPC",
        "Nasdaq": "^IXIC",
        "Russell2000": "^RUT",
        "VIX": "^VIX",
        "US10Y": "^TNX",
        "DXY": "DX-Y.NYB",
        "TAIEX": "^TWII",
        "TPEx": "^TWOII",
        "QQQ": "QQQ",
        "SPY": "SPY",
    }
    hists = download_history(list(symbols.values()), period="3mo", interval="1d")
    out: dict[str, dict[str, Any]] = {}
    for name, symbol in symbols.items():
        hist = hists.get(symbol)
        if hist is None or len(hist) < 2:
            continue
        last = hist.iloc[-1]
        prev = hist.iloc[-2]
        out[name] = {
            "symbol": symbol,
            "close": float(last["Close"]),
            "change_pct": float((last["Close"] / prev["Close"] - 1) * 100),
            "date": str(hist.index[-1].date()),
        }
    return out
