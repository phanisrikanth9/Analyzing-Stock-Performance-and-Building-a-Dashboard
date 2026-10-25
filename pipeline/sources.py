"""Where raw data comes from.

YahooSource is used in production (GitHub Actions). FixtureSource replays a real
snapshot (closes from 2021-10-25 to 2026-10-22) so the whole pipeline runs offline
and in tests without network access.
"""
from __future__ import annotations

import datetime as dt
from typing import Protocol

import pandas as pd

from .config import FIXTURES

PRICE_COLUMNS = ["ticker", "date", "open", "high", "low", "close", "adj_close", "volume", "dividend", "split_ratio"]
REVENUE_COLUMNS = ["ticker", "period_end", "revenue"]


class Source(Protocol):
    name: str

    def prices(self, ticker: str, start: dt.date, end: dt.date) -> pd.DataFrame: ...

    def revenue(self, ticker: str) -> pd.DataFrame: ...


class YahooSource:
    """Daily prices and quarterly revenue from Yahoo Finance via yfinance.

    Prices are stored *unadjusted for dividends* (auto_adjust=False) with dividends and
    splits as separate columns. Yahoo's Close is split-adjusted, so a new split rewrites
    history; ingest detects that and reloads the ticker (see ingest.detect_restatement).
    """

    name = "yahoo"

    def prices(self, ticker: str, start: dt.date, end: dt.date) -> pd.DataFrame:
        import yfinance as yf

        raw = yf.Ticker(ticker).history(
            start=start.isoformat(), end=(end + dt.timedelta(days=1)).isoformat(), auto_adjust=False, actions=True
        )
        if raw.empty:
            return pd.DataFrame(columns=PRICE_COLUMNS)
        raw.index = raw.index.tz_localize(None) if raw.index.tz is not None else raw.index
        df = pd.DataFrame(
            {
                "ticker": ticker,
                "date": raw.index.date,
                "open": raw["Open"].to_numpy(),
                "high": raw["High"].to_numpy(),
                "low": raw["Low"].to_numpy(),
                "close": raw["Close"].to_numpy(),
                "adj_close": (raw["Adj Close"] if "Adj Close" in raw else raw["Close"]).to_numpy(),
                "volume": raw["Volume"].to_numpy(),
                "dividend": raw["Dividends"].to_numpy() if "Dividends" in raw else 0.0,
                "split_ratio": raw["Stock Splits"].to_numpy() if "Stock Splits" in raw else 0.0,
            }
        )
        return df[PRICE_COLUMNS]

    def revenue(self, ticker: str) -> pd.DataFrame:
        import yfinance as yf

        stmt = yf.Ticker(ticker).quarterly_income_stmt
        if stmt is None or stmt.empty or "Total Revenue" not in stmt.index:
            return pd.DataFrame(columns=REVENUE_COLUMNS)
        s = stmt.loc["Total Revenue"].dropna()
        return pd.DataFrame({"ticker": ticker, "period_end": pd.to_datetime(s.index).date, "revenue": s.to_numpy(float)})


class FixtureSource:
    """Real closes captured from Yahoo on 2026-10-22, replayed offline.

    The snapshot has closes only, so open/high/low equal close and volume is unknown.
    ETFs not in the snapshot (the SPY benchmark) return nothing.
    """

    name = "fixture"

    def __init__(self) -> None:
        self._closes = pd.read_csv(FIXTURES / "closes_2021-10-25_2026-10-22.csv.gz", parse_dates=["date"])
        self._revenue = pd.read_csv(FIXTURES / "revenue.csv", parse_dates=["period_end"])

    def prices(self, ticker: str, start: dt.date, end: dt.date) -> pd.DataFrame:
        c = self._closes
        c = c[(c.ticker == ticker) & (c.date.dt.date >= start) & (c.date.dt.date <= end)]
        return pd.DataFrame(
            {
                "ticker": ticker,
                "date": c.date.dt.date.to_numpy(),
                "open": c.close.to_numpy(),
                "high": c.close.to_numpy(),
                "low": c.close.to_numpy(),
                "close": c.close.to_numpy(),
                "adj_close": c.close.to_numpy(),
                "volume": pd.array([pd.NA] * len(c), dtype="Int64"),
                "dividend": 0.0,
                "split_ratio": 0.0,
            }
        )[PRICE_COLUMNS]

    def revenue(self, ticker: str) -> pd.DataFrame:
        r = self._revenue[self._revenue.ticker == ticker]
        return pd.DataFrame({"ticker": ticker, "period_end": r.period_end.dt.date.to_numpy(), "revenue": r.revenue.to_numpy()})


def get_source(name: str) -> Source:
    if name == "yahoo":
        return YahooSource()
    if name == "fixture":
        return FixtureSource()
    raise ValueError(f"unknown source {name!r}")
