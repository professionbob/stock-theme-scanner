# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from scanner.config import env, load_config
from scanner.data import download_history, fetch_market_snapshot, get_finnhub_company_news, get_info, get_news_yf
from scanner.report import render_full_report, save_report
from scanner.scoring import Candidate, score_candidate
from scanner.telegram import send_telegram
from scanner.universe import build_universe, tickers_by_market


def scan_market(raw: dict[str, Any], market: str, universe: dict, histories: dict, benchmark_hist) -> list[Candidate]:
    tickers = tickers_by_market(universe, market)
    candidates: list[Candidate] = []
    finnhub_key = env("FINNHUB_API_KEY")

    print(f"[{market}] 掃描 {len(tickers)} 檔...")
    for i, ticker in enumerate(tickers, start=1):
        hist = histories.get(ticker)
        if hist is None or hist.empty:
            continue

        # get_info 呼叫太頻繁容易被限流；只對技術初篩可能通過的標的呼叫。
        info = {}
        news = []
        try:
            # 先用 yfinance 的 info / news。若限流失敗，scanner 仍可用技術分數跑完。
            info = get_info(ticker)
            news = get_news_yf(ticker, limit=6)
            if market == "US":
                news += get_finnhub_company_news(ticker, finnhub_key, days=14)
        except Exception as exc:
            print(f"{ticker} 基本面/新聞抓取失敗：{exc}")

        c = score_candidate(
            ticker=ticker,
            meta=universe[ticker],
            hist=hist,
            benchmark_hist=benchmark_hist,
            info=info,
            news=news,
            raw_config=raw,
        )
        if c:
            candidates.append(c)
        if i % 25 == 0:
            print(f"[{market}] 已掃描 {i}/{len(tickers)}")

    candidates.sort(key=lambda x: (x.grade != "S", x.grade != "A", -x.score, -x.rr))
    # 先用分數排序，過濾留給 report 層決定是否硬湊。
    candidates = sorted(candidates, key=lambda x: x.score, reverse=True)
    return candidates


def run_once(config_path: str | Path = "config.yaml", market_override: str | None = None, send: bool | None = None) -> str:
    cfg = load_config(config_path)
    raw = cfg.raw
    market = (market_override or raw.get("runtime", {}).get("market", "all")).upper()
    if market == "ALL":
        market = "all"

    universe = build_universe(raw, market=market)
    all_tickers = list(universe.keys())
    benchmarks = raw.get("benchmarks", {}) or {}
    bench_tickers = [benchmarks.get("US", "QQQ"), benchmarks.get("TW", "^TWII")]
    all_download = sorted(set(all_tickers + bench_tickers))

    print(f"開始下載行情，總標的 {len(all_tickers)} 檔，時間：{datetime.now():%Y-%m-%d %H:%M:%S}")
    histories = download_history(all_download, period="1y", interval="1d")
    snapshot = fetch_market_snapshot()

    us_bench = histories.get(benchmarks.get("US", "QQQ"))
    tw_bench = histories.get(benchmarks.get("TW", "^TWII"))

    tw_candidates: list[Candidate] = []
    us_candidates: list[Candidate] = []
    if market in ("all", "TW"):
        tw_candidates = scan_market(raw, "TW", universe, histories, tw_bench)
    if market in ("all", "US"):
        us_candidates = scan_market(raw, "US", universe, histories, us_bench)

    report = render_full_report(
        raw,
        snapshot,
        tw_candidates,
        us_candidates,
        top_n=cfg.top_pool_count,
        recommended_n=cfg.recommended_count_per_market,
    )
    path = save_report(report, cfg.output_dir)
    print(f"報告已輸出：{path}")

    do_send = cfg.telegram_enabled if send is None else send
    if do_send:
        send_telegram(report)

    if cfg.console_enabled:
        print(report[:5000])
        if len(report) > 5000:
            print("\n...完整內容請看報告檔或 Telegram。")
    return report


def run_loop(config_path: str | Path = "config.yaml", market_override: str | None = None) -> None:
    cfg = load_config(config_path)
    interval = int(cfg.raw.get("runtime", {}).get("scan_interval_seconds", 300))
    while True:
        try:
            run_once(config_path, market_override=market_override)
        except KeyboardInterrupt:
            print("手動停止。")
            break
        except Exception as exc:
            print(f"主迴圈錯誤：{exc}")
        time.sleep(interval)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI 主題股票掃描器：台股/美股技術 + 基本 + 資金 + 催化 + 風控")
    parser.add_argument("--config", default="config.yaml", help="設定檔路徑")
    parser.add_argument("--market", default=None, choices=["all", "TW", "US", "tw", "us"], help="掃描市場")
    parser.add_argument("--once", action="store_true", help="只跑一次")
    parser.add_argument("--loop", action="store_true", help="依 config 的 scan_interval_seconds 持續掃描")
    parser.add_argument("--no-send", action="store_true", help="不發 Telegram，只輸出報告")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.loop:
        run_loop(args.config, market_override=args.market)
    else:
        run_once(args.config, market_override=args.market, send=not args.no_send)
