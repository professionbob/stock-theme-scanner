# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import os
import yaml
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AppConfig:
    raw: dict[str, Any]
    path: Path

    @property
    def timezone(self) -> str:
        return self.raw.get("runtime", {}).get("timezone", "Asia/Taipei")

    @property
    def market(self) -> str:
        return self.raw.get("runtime", {}).get("market", "all")

    @property
    def max_candidates_per_market(self) -> int:
        # Backward compatible: 舊設定仍可用，但新版報告主要使用 top_pool_count / recommended_count_per_market。
        return int(self.raw.get("runtime", {}).get("max_candidates_per_market", 3))

    @property
    def top_pool_count(self) -> int:
        return int(self.raw.get("runtime", {}).get("top_pool_count", 10))

    @property
    def recommended_count_per_market(self) -> int:
        runtime = self.raw.get("runtime", {})
        return int(runtime.get("recommended_count", runtime.get("recommended_count_per_market", 3)))

    @property
    def output_dir(self) -> Path:
        return Path(self.raw.get("runtime", {}).get("output_dir", "reports"))

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.raw.get("runtime", {}).get("enable_telegram", True))

    @property
    def console_enabled(self) -> bool:
        return bool(self.raw.get("runtime", {}).get("enable_console", True))


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"找不到設定檔：{config_path.resolve()}")
    with config_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return AppConfig(raw=raw, path=config_path)


def env(name: str, default: str | None = None) -> str | None:
    return os.getenv(name, default)
