# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .scoring import Candidate


def _bullets(items: list[str], empty: str = "資料不足，保守看待") -> str:
    if not items:
        return f"- {empty}"
    return "\n".join(f"- {x}" for x in items)


def classify_market_risk(snapshot: dict[str, dict[str, Any]]) -> tuple[str, str, str]:
    vix = snapshot.get("VIX", {}).get("close")
    ndx_chg = snapshot.get("Nasdaq", {}).get("change_pct")
    spx_chg = snapshot.get("S&P500", {}).get("change_pct")
    us10y_chg = snapshot.get("US10Y", {}).get("change_pct")
    taiex_chg = snapshot.get("TAIEX", {}).get("change_pct")

    risk_off_points = 0
    risk_on_points = 0

    if vix is not None:
        if vix >= 24:
            risk_off_points += 2
        elif vix <= 16:
            risk_on_points += 1
    for chg in (ndx_chg, spx_chg, taiex_chg):
        if chg is None:
            continue
        if chg <= -1.2:
            risk_off_points += 1
        elif chg >= 0.8:
            risk_on_points += 1
    if us10y_chg is not None and us10y_chg >= 2.0:
        risk_off_points += 1

    if risk_off_points >= 2:
        return "Risk-Off", "防守", "大盤風險偏高，優先控部位、降低追價意願。"
    if risk_on_points >= 2:
        return "Risk-On", "積極但不追高", "風險偏好尚可，可做強勢族群，但仍需等合理買點。"
    return "Neutral", "中性", "市場沒有明顯單邊訊號，採取精選標的、分批進場。"


def render_market_overview(snapshot: dict[str, dict[str, Any]]) -> str:
    risk, tone, comment = classify_market_risk(snapshot)
    lines = ["【今日市場總覽】"]
    for name in ["TAIEX", "TPEx", "S&P500", "Nasdaq", "Russell2000", "VIX", "US10Y", "DXY"]:
        item = snapshot.get(name)
        if not item:
            continue
        lines.append(f"- {name}: {item['close']:.2f} / {item['change_pct']:+.2f}%（{item['date']}）")
    lines.extend([
        f"- 市場風險偏好：{risk}",
        f"- 今日操作基調：{tone}",
        f"- 研究員備註：{comment}",
    ])
    return "\n".join(lines)


def _tag_for_rank(rank: int, recommended_n: int) -> str:
    return "⭐ 推薦候選" if rank <= recommended_n else "觀察名單"


def _ranked(candidates: list[Candidate]) -> list[Candidate]:
    # 先排除流動性/資料不足造成沒有 Candidate 的標的；Candidate 內已完成最低流動性過濾。
    # 排序權重：分數為主，RR 為輔，最後避免把純 Watch 放太前面。
    return sorted(
        candidates,
        key=lambda x: (
            x.grade == "Watch",
            x.action == "觀察",
            -x.score,
            -x.rr,
        ),
    )


def render_candidate(c: Candidate, rank: int | None = None, recommended_n: int = 3) -> str:
    prefix = f"第 {rank} 名｜{_tag_for_rank(rank, recommended_n)}" if rank else ""
    title = f"【{prefix}｜{c.ticker}】" if prefix else f"【{c.ticker}】"
    return f"""{title}

1. 市場：{c.market}
2. 產業：{c.industry}
3. 今日結論：{c.action}
4. 信心等級：{c.grade}（總分 {c.score}；技術/基本/資金/催化：{c.metrics['score_parts']}）
5. 現價：{c.price}
6. 建議進場區間：{c.entry_low}～{c.entry_high}
7. 加碼區間：{c.add_low}～{c.add_high}
8. 停損位置：{c.stop}
9. 第一目標價：{c.target1}
10. 第二目標價：{c.target2}
11. 預估上漲空間：{c.upside_pct}%
12. 預估下跌風險：{c.downside_pct}%
13. 風險報酬比：{c.rr}
14. 建議持有週期：{c.holding_period}
15. 建議投入比例：{c.position_pct}
16. 技術面理由：
{_bullets(c.technical_reasons)}
17. 基本面理由：
{_bullets(c.fundamental_reasons)}
18. 籌碼 / 資金面理由：
{_bullets(c.flow_reasons)}
19. 新聞 / 政策催化劑：
{_bullets(c.catalyst_reasons)}
20. 三個月內達到 10% 報酬的可能路徑：
- {c.path_to_10pct}
21. 失敗條件：
{_bullets(c.failure_conditions)}
22. 需要追蹤的關鍵日期或事件：
{_bullets(c.key_events)}
23. 主要風險：
{_bullets(c.risks)}"""


def render_top_pool_table(candidates: list[Candidate], top_n: int = 10, recommended_n: int = 3) -> str:
    ranked = _ranked(candidates)[:top_n]
    if not ranked:
        return "股票池 Top 排名：今日資料不足，沒有可排序標的。"

    lines = [f"股票池 Top {len(ranked)} 排名（前 {min(recommended_n, len(ranked))} 名標示為推薦候選，其餘只列觀察）："]
    header = "| 排名 | 標記 | 股票代號 | 市場 | 主題 | 現價 | 分數 | 等級 | 今日動作 | RR | 買點 | 停損 | 目標1 |"
    sep = "|---:|---|---|---|---|---:|---:|---|---|---:|---|---:|---:|"
    lines.extend([header, sep])
    for i, c in enumerate(ranked, start=1):
        theme = ", ".join(c.themes[:2])
        tag = _tag_for_rank(i, recommended_n)
        lines.append(
            f"| {i} | {tag} | {c.ticker} | {c.market} | {theme} | {c.price} | {c.score} | {c.grade} | {c.action} | {c.rr} | {c.entry_low}～{c.entry_high} | {c.stop} | {c.target1} |"
        )
    return "\n".join(lines)


def render_market_section(title: str, candidates: list[Candidate], top_n: int = 10, recommended_n: int = 3) -> str:
    ranked = _ranked(candidates)
    if not ranked:
        return f"【{title}】\n今日資料不足，沒有可排序標的，不硬湊名單。"

    top_list = ranked[:top_n]
    recommended = top_list[:recommended_n]
    sections = [
        f"【{title}】",
        render_top_pool_table(top_list, top_n=top_n, recommended_n=recommended_n),
        f"以下只詳細展開前 {len(recommended)} 檔推薦候選；第 {len(recommended) + 1}～{len(top_list)} 名只列入觀察，不視為正式買進建議。",
    ]
    sections.extend(render_candidate(c, rank=i, recommended_n=recommended_n) for i, c in enumerate(recommended, start=1))
    return "\n\n".join(sections)


def render_portfolio_check(raw: dict, by_ticker: dict[str, Candidate]) -> str:
    portfolio = raw.get("portfolio", []) or []
    if not portfolio:
        return "【持股與觀察名單檢查】\n尚未設定 portfolio，請在 config.yaml 補上持股、成本、停損與目標價。"
    lines = ["【持股與觀察名單檢查】"]
    for item in portfolio:
        ticker = str(item.get("ticker", "")).upper()
        if not ticker:
            continue
        c = by_ticker.get(ticker)
        if not c:
            lines.append(f"- {ticker}: 今日資料不足或不在可掃描結果內，維持原停損檢查。")
            continue
        stop = float(item.get("stop") or c.stop)
        target1 = float(item.get("target1") or c.target1)
        target2 = float(item.get("target2") or c.target2)
        if c.price <= stop:
            action = "停損"
        elif c.price >= target2:
            action = "停利 / 提高移動停利線"
        elif c.price >= target1:
            action = "部分停利 / 移動停利"
        elif c.grade in {"S", "A"} and c.action in {"可進場", "等回測"}:
            action = "持有"
        elif c.grade == "Watch":
            action = "觀望 / 不加碼"
        else:
            action = "持有但不追價"
        lines.append(f"- {ticker}: {action}。現價 {c.price}，停損 {stop}，目標 {target1}/{target2}，等級 {c.grade}。")
    return "\n".join(lines)


def render_action_plan(candidates: list[Candidate], recommended_n: int = 3) -> str:
    ranked = _ranked(candidates)
    recommended = ranked[:recommended_n]
    recommended_tickers = {c.ticker for c in recommended}
    groups = {
        "今日特別標示的推薦候選": [c.ticker for c in recommended],
        "其中可直接買進的標的": [c.ticker for c in recommended if c.action == "可進場" and c.grade in {"S", "A"}],
        "其中需要等回測的標的": [c.ticker for c in recommended if c.action == "等回測"],
        "可以加碼的標的": [c.ticker for c in recommended if c.grade == "S" and c.action == "可進場"],
        "需要減碼的標的": [c.ticker for c in candidates if c.ticker in recommended_tickers and c.metrics.get("distance_ema20_pct", 0) > 10],
        "需要停利的標的": [],
        "需要停損的標的": [],
        "只觀察不動作的 Top 10 標的": [c.ticker for c in ranked[:10] if c.ticker not in recommended_tickers],
    }
    lines = ["【今日操作計畫】"]
    for name, tickers in groups.items():
        lines.append(f"- {name}：{', '.join(tickers) if tickers else '無'}")
    return "\n".join(lines)


def render_summary_table(candidates: list[Candidate], max_rows: int = 20, recommended_n: int = 3) -> str:
    ranked = _ranked(candidates)[:max_rows]
    lines = ["【總表】"]
    header = "| 排名 | 標記 | 股票代號 | 市場 | 產業/主題 | 現價 | 建議買點 | 停損 | 目標1 | 目標2 | 建議投入 | RR | 等級 | 今日動作 |"
    sep = "|---:|---|---|---|---|---:|---|---:|---:|---:|---|---:|---|---|"
    lines.extend([header, sep])
    for i, c in enumerate(ranked, start=1):
        theme = ", ".join(c.themes[:2])
        lines.append(
            f"| {i} | {_tag_for_rank(i, recommended_n)} | {c.ticker} | {c.market} | {theme} | {c.price} | {c.entry_low}～{c.entry_high} | {c.stop} | {c.target1} | {c.target2} | {c.position_pct} | {c.rr} | {c.grade} | {c.action} |"
        )
    return "\n".join(lines)


def render_full_report(
    raw: dict,
    snapshot: dict[str, dict[str, Any]],
    tw_candidates: list[Candidate],
    us_candidates: list[Candidate],
    top_n: int | None = None,
    recommended_n: int | None = None,
) -> str:
    runtime = raw.get("runtime", {}) or {}
    top_n = int(top_n or runtime.get("top_pool_count", 10))
    recommended_n = int(recommended_n or runtime.get("recommended_count", runtime.get("recommended_count_per_market", 3)))
    all_candidates = _ranked(tw_candidates + us_candidates)
    by_ticker = {c.ticker.upper(): c for c in all_candidates}
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    sections = [
        f"# AI 主題選股掃描報告\n\n產出時間：{now}\n\n說明：本報告是候選清單與風控計畫，不保證獲利，也不是直接投資指令。新版輸出會把全股票池 Top {top_n} 都列出，但只把前 {recommended_n} 檔標示為推薦候選，其餘列為觀察。",
        render_market_overview(snapshot),
        render_market_section("今日全股票池排名", all_candidates, top_n=top_n, recommended_n=recommended_n),
        render_portfolio_check(raw, by_ticker),
        render_action_plan(all_candidates, recommended_n=recommended_n),
        render_summary_table(all_candidates, max_rows=top_n, recommended_n=recommended_n),
    ]
    return "\n\n".join(sections)


def save_report(report: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = datetime.now().strftime("scanner_report_%Y%m%d_%H%M.md")
    path = output_dir / filename
    path.write_text(report, encoding="utf-8")
    return path
