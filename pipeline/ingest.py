"""Extract + load: pull prices and revenue into the raw layer (one Parquet file per ticker).

Properties that matter:
- Incremental: only the last few days are fetched once a ticker has history.
- Idempotent: re-running on the same day changes nothing (upsert on ticker + date).
- Restatement-safe: Yahoo rewrites history after splits and dividends. If the overlap
  window disagrees with what is stored, the ticker is reloaded from scratch instead of
  silently mixing two price bases.
- Atomic writes: a crash never leaves a half-written file.
- One bad ticker does not stop the others; its error is recorded in the manifest.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .config import RAW, Universe
from .sources import PRICE_COLUMNS, REVENUE_COLUMNS, Source

OVERLAP_DAYS = 7
RESTATEMENT_TOLERANCE = 1e-4  # relative difference in close / adj_close


@dataclass
class LoadResult:
    ticker: str
    mode: str  # backfill | incremental | reload | unchanged | failed
    rows_before: int = 0
    rows_after: int = 0
    new_rows: int = 0
    last_date: str | None = None
    error: str | None = None
    notes: list[str] = field(default_factory=list)


def read_raw(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=columns)
    return pd.read_parquet(path)


def write_atomic(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)


def normalize_prices(df: pd.DataFrame) -> pd.DataFrame:
    out = df[PRICE_COLUMNS].copy()
    out["date"] = pd.to_datetime(out["date"]).dt.date
    for c in ["open", "high", "low", "close", "adj_close", "dividend", "split_ratio"]:
        out[c] = pd.to_numeric(out[c], errors="coerce").astype("float64")
    out["volume"] = pd.to_numeric(out["volume"], errors="coerce").astype("Int64")
    out = out.dropna(subset=["close"])
    return out.sort_values("date").drop_duplicates(["ticker", "date"], keep="last").reset_index(drop=True)


def upsert(existing: pd.DataFrame, new: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """New rows win over existing rows with the same keys."""
    if existing.empty:
        return new.reset_index(drop=True)
    if new.empty:
        return existing.reset_index(drop=True)
    both = pd.concat([existing, new], ignore_index=True)
    return both.drop_duplicates(keys, keep="last").sort_values(keys).reset_index(drop=True)


def detect_restatement(existing: pd.DataFrame, new: pd.DataFrame) -> bool:
    """True if prices for dates we already have changed (split or dividend re-basing)."""
    if existing.empty or new.empty:
        return False
    m = existing.merge(new, on=["ticker", "date"], suffixes=("_old", "_new"))
    if m.empty:
        return False
    for col in ("close", "adj_close"):
        old, nw = m[f"{col}_old"].to_numpy(float), m[f"{col}_new"].to_numpy(float)
        rel = np.abs(nw - old) / np.maximum(np.abs(old), 1e-9)
        if np.nanmax(rel) > RESTATEMENT_TOLERANCE:
            return True
    return False


def ingest_prices(source: Source, ticker: str, today: dt.date, years: int, raw_dir: Path = RAW) -> LoadResult:
    path = raw_dir / "prices" / f"{ticker}.parquet"
    existing = read_raw(path, PRICE_COLUMNS)
    if not existing.empty:
        existing = normalize_prices(existing)
    res = LoadResult(ticker=ticker, mode="backfill", rows_before=len(existing))
    history_start = today - dt.timedelta(days=int(365.25 * years))
    try:
        if existing.empty:
            merged = normalize_prices(source.prices(ticker, history_start, today))
        else:
            last = max(existing["date"])
            new = normalize_prices(source.prices(ticker, last - dt.timedelta(days=OVERLAP_DAYS), today))
            if detect_restatement(existing, new):
                res.mode = "reload"
                res.notes.append("history changed upstream (split or dividend); reloaded")
                merged = normalize_prices(source.prices(ticker, history_start, today))
            else:
                merged = upsert(existing, new, ["ticker", "date"])
        # Keep a rolling window so the raw layer does not grow forever.
        merged = merged[merged["date"] >= history_start].reset_index(drop=True)
        if merged.empty:
            raise RuntimeError("source returned no rows")
        known = set(existing["date"]) if res.mode != "reload" else set()
        res.new_rows = sum(d not in known for d in merged["date"])
        if res.mode == "backfill" and not existing.empty:
            res.mode = "incremental" if res.new_rows or len(merged) != len(existing) else "unchanged"
        if res.mode != "unchanged":
            write_atomic(merged, path)
        res.rows_after = len(merged)
        res.last_date = str(max(merged["date"]))
    except Exception as e:  # recorded, the run carries on with the other tickers
        res.mode = "failed"
        res.error = f"{type(e).__name__}: {e}"
        res.rows_after = len(existing)
        res.last_date = str(max(existing["date"])) if not existing.empty else None
    return res


def ingest_revenue(source: Source, tickers: list[str], raw_dir: Path = RAW) -> int:
    path = raw_dir / "revenue.parquet"
    existing = read_raw(path, REVENUE_COLUMNS)
    frames = []
    for t in tickers:
        try:
            frames.append(source.revenue(t))
        except Exception as e:
            print(f"  revenue for {t} unavailable: {e}")
    new = pd.concat([f for f in frames if not f.empty], ignore_index=True) if any(not f.empty for f in frames) else pd.DataFrame(columns=REVENUE_COLUMNS)
    for df in (existing, new):
        if not df.empty:
            df["period_end"] = pd.to_datetime(df["period_end"]).dt.date
            df["revenue"] = df["revenue"].astype(float)
    merged = upsert(existing, new, ["ticker", "period_end"])
    if not merged.empty:
        write_atomic(merged, path)
    return len(merged)


def run_ingest(source: Source, universe: Universe, today: dt.date | None = None, raw_dir: Path = RAW) -> dict:
    today = today or dt.date.today()
    results = []
    for t in universe.symbols:
        r = ingest_prices(source, t, today, universe.history_years, raw_dir)
        print(f"  {t:<5} {r.mode:<11} rows {r.rows_before:>5} -> {r.rows_after:>5}  last {r.last_date}  {r.error or ''}")
        results.append(r)
    revenue_rows = ingest_revenue(source, [t.symbol for t in universe.tickers if t.symbol != universe.benchmark], raw_dir)
    manifest = {
        "ingested_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "as_of": today.isoformat(),
        "source": source.name,
        "prices": [asdict(r) for r in results],
        "revenue_rows": revenue_rows,
    }
    (raw_dir / "_manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest
