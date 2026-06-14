# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import math

import numpy as np
import pandas as pd

from .indicators import add_indicators, detect_patterns
from .universe import TickerMeta


@dataclass
class Candidate:
    ticker: str
    market: str
    themes: tuple[str, ...]
    score: float
    grade: str
    action: str
    price: float
    entry_low: float
    entry_high: float
    add_low: float
    add_high: float
    stop: float
    target1: float
    target2: float
    upside_pct: float
    downside_pct: float
    rr: float
    position_pct: str
    holding_period: str
    industry: str
    technical_reasons: list[str]
    fundamental_reasons: list[str]
    flow_reasons: list[str]
    catalyst_reasons: list[str]
    path_to_10pct: str
    failure_conditions: list[str]
    key_events: list[str]
    risks: list[str]
    patterns: list[str]
    metrics: dict[str, Any]


def _safe_float(x: Any, default: float = float("nan")) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def _fmt_pct_range(raw: dict, grade: str) -> str:
    risk = raw.get("risk", {}) or {}
    if grade == "S":
        lo, hi = risk.get("s_position_pct", [10, 15])
    elif grade == "A":
        lo, hi = risk.get("a_position_pct", [5, 10])
    elif grade == "B":
        lo, hi = risk.get("b_position_pct", [3, 5])
    else:
        lo, hi = risk.get("watch_position_pct", [0, 0])
    return f"{lo}%～{hi}%" if hi else "0%，僅觀察"


def _news_text(news: list[dict[str, Any]]) -> str:
    texts: list[str] = []
    for item in news or []:
        for key in ("title", "headline", "summary"):
            if item.get(key):
                texts.append(str(item[key]))
    return " | ".join(texts).lower()


def _news_titles(news: list[dict[str, Any]], limit: int = 3) -> list[str]:
    titles = []
    for item in news or []:
        title = item.get("title") or item.get("headline")
        if title:
            titles.append(str(title))
    return titles[:limit]


def _calc_relative_strength(hist: pd.DataFrame, bench: pd.DataFrame | None) -> float:
    if bench is None or bench.empty or len(hist) < 63 or len(bench) < 63:
        return 0.0
    stock_ret = hist["Close"].iloc[-1] / hist["Close"].iloc[-63] - 1
    bench_ret = bench["Close"].iloc[-1] / bench["Close"].iloc[-63] - 1
    return float((stock_ret - bench_ret) * 100)


def _build_risk_plan(df: pd.DataFrame, raw: dict) -> dict[str, float]:
    latest = df.iloc[-1]
    close = float(latest["Close"])
    atr = _safe_float(latest.get("ATR14"), close * 0.05)
    sma20 = _safe_float(latest.get("SMA20"), close)
    ema20 = _safe_float(latest.get("EMA20"), close)
    low20 = _safe_float(latest.get("LOW20"), close * 0.93)
    high20 = _safe_float(latest.get("HIGH20"), close * 1.06)
    high60 = _safe_float(latest.get("HIGH60"), close * 1.10)

    # 不追高：進場區間盡量貼近 EMA20 / 近 5 日區間，不直接追遠離均線的價格。
    entry_low = max(min(close * 0.985, ema20 * 1.015), close * 0.92)
    entry_high = min(close * 1.005, max(close, ema20 * 1.035))

    # 加碼：突破 20 日高且放量，或回測 EMA20 不破後轉強。
    add_low = max(high20 * 0.995, close * 1.01)
    add_high = add_low * 1.025

    # 停損：用 20 日低點 / EMA20 - 1.2ATR / 進場價 - 1.8ATR 取合理防線。
    stop_candidates = [low20 * 0.985, ema20 - 1.2 * atr, close - 1.8 * atr]
    stop = max([x for x in stop_candidates if x > 0], default=close * 0.92)
    if stop >= close:
        stop = close * 0.93

    risk_per_share = max(close - stop, atr * 0.8)
    target1 = max(close + 2 * risk_per_share, high20 * 1.03)
    target2 = max(close + 3 * risk_per_share, high60 * 1.05)

    rr = (target1 - close) / max(close - stop, 0.01)
    return {
        "entry_low": round(entry_low, 2),
        "entry_high": round(entry_high, 2),
        "add_low": round(add_low, 2),
        "add_high": round(add_high, 2),
        "stop": round(stop, 2),
        "target1": round(target1, 2),
        "target2": round(target2, 2),
        "upside_pct": round((target1 / close - 1) * 100, 1),
        "downside_pct": round((1 - stop / close) * 100, 1),
        "rr": round(rr, 2),
    }


def score_candidate(
    ticker: str,
    meta: TickerMeta,
    hist: pd.DataFrame,
    benchmark_hist: pd.DataFrame | None,
    info: dict[str, Any],
    news: list[dict[str, Any]],
    raw_config: dict,
) -> Candidate | None:
    df = add_indicators(hist)
    if len(df) < 80:
        return None
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    price = _safe_float(latest["Close"])
    if not math.isfinite(price) or price <= 0:
        return None

    risk_cfg = raw_config.get("risk", {}) or {}
    avg_vol = _safe_float(df["Volume"].tail(20).mean(), 0)
    turnover = avg_vol * price
    if meta.market == "US":
        if price < float(risk_cfg.get("min_price_usd", 2.0)):
            return None
        if avg_vol < float(risk_cfg.get("min_avg_volume_us", 500000)) and turnover < float(risk_cfg.get("min_avg_turnover_usd", 5000000)):
            return None
    else:
        if avg_vol < float(risk_cfg.get("min_avg_volume_tw", 500000)) and turnover < float(risk_cfg.get("min_avg_turnover_twd", 30000000)):
            return None

    rsi = _safe_float(latest.get("RSI14"), 50)
    atr_pct = _safe_float(latest.get("ATR_PCT"), 99)
    vol_ratio = _safe_float(latest.get("VOL_RATIO"), 1)
    macd_hist = _safe_float(latest.get("MACD_HIST"), 0)
    ma20_slope = _safe_float(latest.get("MA20_SLOPE"), 0)
    ema20 = _safe_float(latest.get("EMA20"), price)
    sma20 = _safe_float(latest.get("SMA20"), price)
    sma50 = _safe_float(latest.get("SMA50"), price)
    sma200 = _safe_float(latest.get("SMA200"), price)
    distance_ema20_pct = (price / ema20 - 1) * 100 if ema20 else 999
    rel_strength = _calc_relative_strength(df, benchmark_hist)
    patterns = detect_patterns(df)

    technical_reasons: list[str] = []
    tech_score = 0
    if price > sma20:
        tech_score += 6; technical_reasons.append("收盤價站上 20 日均線")
    if price > sma50:
        tech_score += 6; technical_reasons.append("收盤價站上 50 日均線")
    if sma20 > sma50:
        tech_score += 5; technical_reasons.append("20MA 高於 50MA，短中期趨勢偏多")
    if ma20_slope > 0:
        tech_score += 5; technical_reasons.append("20MA 斜率轉正")
    if 52 <= rsi <= 72:
        tech_score += 6; technical_reasons.append(f"RSI {rsi:.1f}，屬於轉強但未極端過熱")
    elif 72 < rsi <= 78:
        tech_score += 2; technical_reasons.append(f"RSI {rsi:.1f} 偏熱，需等回測")
    if macd_hist > 0 and macd_hist >= _safe_float(prev.get("MACD_HIST"), 0):
        tech_score += 5; technical_reasons.append("MACD 柱狀體為正且未轉弱")
    if vol_ratio >= 1.3:
        tech_score += 5; technical_reasons.append(f"成交量約為 20 日均量 {vol_ratio:.1f} 倍")
    if rel_strength > 3:
        tech_score += 5; technical_reasons.append(f"近 3 個月相對強於基準約 {rel_strength:.1f} 個百分點")
    if patterns:
        tech_score += min(7, 2 * len(patterns)); technical_reasons.extend(patterns)
    tech_score = min(45, tech_score)

    fundamental_reasons: list[str] = []
    fund_score = 0
    revenue_growth = _safe_float(info.get("revenueGrowth"))
    earnings_growth = _safe_float(info.get("earningsGrowth"))
    gross_margin = _safe_float(info.get("grossMargins"))
    operating_margin = _safe_float(info.get("operatingMargins"))
    free_cashflow = _safe_float(info.get("freeCashflow"))
    debt_to_equity = _safe_float(info.get("debtToEquity"))
    forward_pe = _safe_float(info.get("forwardPE"))

    if math.isfinite(revenue_growth) and revenue_growth > 0.05:
        fund_score += 6; fundamental_reasons.append(f"營收成長率約 {revenue_growth*100:.1f}%")
    if math.isfinite(earnings_growth) and earnings_growth > 0.05:
        fund_score += 5; fundamental_reasons.append(f"獲利成長率約 {earnings_growth*100:.1f}%")
    if math.isfinite(gross_margin) and gross_margin > 0.25:
        fund_score += 4; fundamental_reasons.append(f"毛利率約 {gross_margin*100:.1f}%")
    if math.isfinite(operating_margin) and operating_margin > 0.08:
        fund_score += 4; fundamental_reasons.append(f"營益率約 {operating_margin*100:.1f}%")
    if math.isfinite(free_cashflow) and free_cashflow > 0:
        fund_score += 3; fundamental_reasons.append("自由現金流為正")
    if math.isfinite(debt_to_equity) and debt_to_equity < 120:
        fund_score += 2; fundamental_reasons.append(f"負債權益比約 {debt_to_equity:.1f}，未明顯失控")
    if math.isfinite(forward_pe) and 0 < forward_pe < 70:
        fund_score += 1; fundamental_reasons.append(f"Forward P/E 約 {forward_pe:.1f}，估值未失真到不可判讀")
    if not fundamental_reasons:
        fundamental_reasons.append("免費資料源基本面欄位不足，基本面分數保守處理")
    fund_score = min(25, fund_score)

    flow_reasons: list[str] = []
    flow_score = 0
    if avg_vol > 0:
        flow_score += 4; flow_reasons.append("流動性符合最低篩選條件")
    if vol_ratio >= 1.2:
        flow_score += 4; flow_reasons.append("量能高於近期均量，資金有回流跡象")
    if rel_strength > 0:
        flow_score += 4; flow_reasons.append("相對強弱優於市場基準")
    held_pct_inst = _safe_float(info.get("heldPercentInstitutions"))
    if math.isfinite(held_pct_inst) and held_pct_inst > 0.25:
        flow_score += 3; flow_reasons.append(f"機構持股比例約 {held_pct_inst*100:.1f}%")
    flow_score = min(15, flow_score)

    catalyst_reasons: list[str] = []
    catalyst_score = 0
    catalyst_text = _news_text(news)
    keywords = raw_config.get("catalyst_keywords", []) or []
    hits = [kw for kw in keywords if kw.lower() in catalyst_text]
    if hits:
        catalyst_score += min(8, len(set(hits)) * 2)
        catalyst_reasons.append("近期新聞命中催化關鍵字：" + ", ".join(sorted(set(hits))[:8]))
    if meta.themes:
        catalyst_score += min(5, meta.theme_score)
        catalyst_reasons.append("主題覆蓋：" + ", ".join(meta.themes))
    recent_titles = _news_titles(news, 2)
    if recent_titles:
        catalyst_score += 2
        catalyst_reasons.extend(["近期新聞：" + t for t in recent_titles])
    catalyst_score = min(15, catalyst_score)

    total = round(tech_score + fund_score + flow_score + catalyst_score, 1)
    plan = _build_risk_plan(df, raw_config)

    overextended = distance_ema20_pct > float(risk_cfg.get("overextended_from_ema20_pct", 8.0))
    too_hot = rsi > float(risk_cfg.get("max_rsi_to_enter", 74))
    too_volatile = atr_pct > float(risk_cfg.get("max_atr_pct", 8.0))
    rr_low = plan["rr"] < float(risk_cfg.get("min_rr_to_recommend", 1.8))

    if total >= 82 and plan["rr"] >= 2.0 and not (overextended or too_hot or too_volatile):
        grade = "S"
        action = "可進場"
    elif total >= 72 and plan["rr"] >= 1.8 and not (overextended or too_volatile):
        grade = "A"
        action = "等回測" if too_hot else "可進場"
    elif total >= 62 and not too_volatile:
        grade = "B"
        action = "觀察" if rr_low or overextended else "等回測"
    else:
        grade = "Watch"
        action = "觀察"

    if overextended:
        action = "等回測"
        technical_reasons.append(f"距離 EMA20 約 {distance_ema20_pct:.1f}%，避免追高")
    if too_volatile:
        action = "觀察"
        technical_reasons.append(f"ATR% 約 {atr_pct:.1f}%，波動偏大，需降低倉位")
    if rr_low:
        action = "觀察"

    risks = []
    if overextended:
        risks.append("短線離均線過遠，追價容易被洗出場")
    if too_hot:
        risks.append("RSI 偏熱，若量縮容易回測")
    if too_volatile:
        risks.append("波動偏大，停損距離可能過遠")
    risks.extend(["大盤轉 Risk-Off 會壓低題材股估值", "財報或法說不如預期會導致重新定價"])

    failure_conditions = [
        f"收盤跌破停損 {plan['stop']}",
        "跌破 20MA 後 2 個交易日內無法收回",
        "放量長黑且跌破前低，代表突破/修復失敗",
    ]

    path = (
        f"先守住進場區 {plan['entry_low']}～{plan['entry_high']}，再放量突破加碼區 "
        f"{plan['add_low']}～{plan['add_high']}；若三個月內主題催化延續且站上第一目標 "
        f"{plan['target1']}，即具備約 {plan['upside_pct']}% 的波段空間。"
    )

    industry = info.get("industry") or info.get("sector") or ", ".join(meta.themes)

    return Candidate(
        ticker=ticker,
        market=meta.market,
        themes=meta.themes,
        score=total,
        grade=grade,
        action=action,
        price=round(price, 2),
        entry_low=plan["entry_low"],
        entry_high=plan["entry_high"],
        add_low=plan["add_low"],
        add_high=plan["add_high"],
        stop=plan["stop"],
        target1=plan["target1"],
        target2=plan["target2"],
        upside_pct=plan["upside_pct"],
        downside_pct=plan["downside_pct"],
        rr=plan["rr"],
        position_pct=_fmt_pct_range(raw_config, grade),
        holding_period="1～3 個月",
        industry=str(industry),
        technical_reasons=technical_reasons[:8],
        fundamental_reasons=fundamental_reasons[:6],
        flow_reasons=flow_reasons[:5],
        catalyst_reasons=catalyst_reasons[:6],
        path_to_10pct=path,
        failure_conditions=failure_conditions,
        key_events=["下一次財報/法說", "重大客戶訂單/資本支出更新", "同族群資金輪動是否延續"],
        risks=risks[:6],
        patterns=patterns,
        metrics={
            "rsi14": round(rsi, 1),
            "atr_pct": round(atr_pct, 1),
            "vol_ratio": round(vol_ratio, 2),
            "rel_strength_3m_pct": round(rel_strength, 1),
            "distance_ema20_pct": round(distance_ema20_pct, 1),
            "score_parts": {
                "technical": tech_score,
                "fundamental": fund_score,
                "flow": flow_score,
                "catalyst": catalyst_score,
            },
        },
    )
