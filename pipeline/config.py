"""Paths and the ticker universe, shared by every pipeline step."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
# Overridable so tests run in a scratch directory and never touch the real raw layer.
RAW = Path(os.environ.get("STOCK_RAW_DIR", ROOT / "warehouse" / "raw"))
WAREHOUSE_DB = Path(os.environ.get("STOCK_WAREHOUSE_DB", ROOT / "warehouse" / "warehouse.duckdb"))
SITE_DATA = Path(os.environ.get("STOCK_SITE_DATA", ROOT / "site" / "public" / "data"))
DBT_DIR = ROOT / "transform"
FIXTURES = ROOT / "tests" / "fixtures"


@dataclass(frozen=True)
class Ticker:
    symbol: str
    name: str
    sector: str
    color: str


@dataclass(frozen=True)
class Universe:
    tickers: tuple[Ticker, ...]
    benchmark: str
    history_years: int

    @property
    def symbols(self) -> list[str]:
        return [t.symbol for t in self.tickers]


def load_universe(path: Path = ROOT / "config" / "tickers.yml") -> Universe:
    cfg = yaml.safe_load(path.read_text())
    tickers = tuple(Ticker(**t) for t in cfg["tickers"])
    symbols = [t.symbol for t in tickers]
    if len(set(symbols)) != len(symbols):
        raise ValueError("duplicate ticker in config/tickers.yml")
    if cfg["benchmark"] not in symbols:
        raise ValueError("the benchmark must also be listed under tickers")
    return Universe(tickers, cfg["benchmark"], int(cfg.get("history_years", 5)))
