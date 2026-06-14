# -*- coding: utf-8 -*-
from __future__ import annotations

import numpy as np
import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def macd(close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    line = ema12 - ema26
    signal = line.ewm(span=9, adjust=False).mean()
    hist = line - signal
    return line, signal, hist


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    close = out["Close"]
    volume = out["Volume"]

    out["SMA20"] = close.rolling(20).mean()
    out["SMA50"] = close.rolling(50).mean()
    out["SMA200"] = close.rolling(200).mean()
    out["EMA20"] = close.ewm(span=20, adjust=False).mean()
    out["RSI14"] = rsi(close, 14)
    out["ATR14"] = atr(out, 14)
    out["ATR_PCT"] = out["ATR14"] / close * 100
    out["VOL20"] = volume.rolling(20).mean()
    out["VOL_RATIO"] = volume / out["VOL20"].replace(0, np.nan)

    macd_line, macd_signal, macd_hist = macd(close)
    out["MACD"] = macd_line
    out["MACD_SIGNAL"] = macd_signal
    out["MACD_HIST"] = macd_hist

    out["HIGH20"] = out["High"].rolling(20).max()
    out["LOW20"] = out["Low"].rolling(20).min()
    out["HIGH60"] = out["High"].rolling(60).max()
    out["LOW60"] = out["Low"].rolling(60).min()
    out["BB_MID"] = out["SMA20"]
    out["BB_STD"] = close.rolling(20).std()
    out["BB_UPPER"] = out["BB_MID"] + 2 * out["BB_STD"]
    out["BB_LOWER"] = out["BB_MID"] - 2 * out["BB_STD"]
    out["MA20_SLOPE"] = out["SMA20"].diff(5)
    out["MA50_SLOPE"] = out["SMA50"].diff(5)
    return out


def detect_patterns(df: pd.DataFrame) -> list[str]:
    if len(df) < 80:
        return []
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    close = latest["Close"]
    patterns: list[str] = []

    if close > latest["SMA20"] > latest["SMA50"] and latest["MA20_SLOPE"] > 0:
        patterns.append("均線多頭排列")

    if close >= prev["HIGH20"] and latest["VOL_RATIO"] >= 1.3:
        patterns.append("20日高放量突破")

    range_60 = (latest["HIGH60"] - latest["LOW60"]) / close if close else np.nan
    range_20 = (latest["HIGH20"] - latest["LOW20"]) / close if close else np.nan
    if pd.notna(range_60) and pd.notna(range_20) and range_20 < range_60 * 0.55 and latest["ATR_PCT"] < 6:
        patterns.append("VCP/波動收斂候選")

    gain_20 = close / df["Close"].iloc[-21] - 1 if len(df) > 21 else 0
    recent_tight = (df["High"].tail(8).max() - df["Low"].tail(8).min()) / close
    if gain_20 > 0.15 and recent_tight < 0.10 and close > latest["EMA20"]:
        patterns.append("強勢旗型整理候選")

    drawdown_60 = 1 - (latest["LOW60"] / latest["HIGH60"]) if latest["HIGH60"] else np.nan
    recovery = close / latest["HIGH60"] if latest["HIGH60"] else np.nan
    if pd.notna(drawdown_60) and drawdown_60 >= 0.15 and recovery >= 0.88 and recent_tight < 0.12:
        patterns.append("杯柄/右側修復候選")

    was_below = (df["Close"].iloc[-30:-15] < df["SMA50"].iloc[-30:-15]).mean() > 0.6
    now_above = close > latest["SMA50"] and latest["MA20_SLOPE"] > 0
    if was_below and now_above:
        patterns.append("底部反轉候選")

    return patterns
