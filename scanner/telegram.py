# -*- coding: utf-8 -*-
from __future__ import annotations

import requests

from .config import env

TELEGRAM_LIMIT = 3900


def _split_message(text: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    chunks: list[str] = []
    current = ""
    for line in text.splitlines(True):
        if len(current) + len(line) > limit:
            if current:
                chunks.append(current)
            current = line
        else:
            current += line
    if current:
        chunks.append(current)
    return chunks


def send_telegram(text: str) -> bool:
    token = env("TELEGRAM_BOT_TOKEN")
    chat_id = env("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram 未設定：請在 .env 填 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")
        return False
    ok = True
    for chunk in _split_message(text):
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        try:
            r = requests.post(url, json=payload, timeout=15)
            if not r.ok:
                # Markdown 可能因特殊字元失敗，降級純文字。
                payload.pop("parse_mode", None)
                r = requests.post(url, json=payload, timeout=15)
            r.raise_for_status()
        except Exception as exc:
            print(f"Telegram 發送失敗：{exc}")
            ok = False
    return ok
