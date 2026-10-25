"""Serve layer: write the marts as compact JSON (for the dashboard) and Parquet (for the
in-browser SQL console), plus a health report describing this run."""
from __future__ import annotations

import datetime as dt
import json
import math

import duckdb

from .config import SITE_DATA, WAREHOUSE_DB

MARTS = ["fct_daily_prices", "mart_ticker_summary", "mart_return_correlation", "fct_quarterly_revenue", "mart_monthly_returns"]


def _clean(v, digits=6):
    if v is None:
        return None
    if isinstance(v, float):
        return None if math.isnan(v) or math.isinf(v) else round(v, digits)
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    return v


def _rows(con, sql: str, digits=6) -> list[dict]:
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return [{c: _clean(v, digits) for c, v in zip(cols, row)} for row in cur.fetchall()]


def export_site(manifest, nodes, freshness, ok, timings, universe) -> None:
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    # dbt runs in-process and may still hold the file open, so use the same (read-write) mode.
    con = duckdb.connect(str(WAREHOUSE_DB))
    try:
        if ok:
            _export_data(con)
        counts = {m: con.execute(f"select count(*) from {m}").fetchone()[0] for m in MARTS if _exists(con, m)}
    finally:
        con.close()

    tests = [n for n in nodes if n["type"] == "test"]
    health = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "status": "ok" if ok else "failed",
        "source": manifest["source"],
        "as_of": manifest["as_of"],
        "ingest": manifest["prices"],
        "revenue_rows": manifest["revenue_rows"],
        "row_counts": counts,
        "tests": {
            "total": len(tests),
            "passed": sum(t["status"] == "pass" for t in tests),
            "warned": sum(t["status"] == "warn" for t in tests),
            "failed": sum(t["status"] in ("fail", "error") for t in tests),
            "details": sorted(tests, key=lambda t: (t["status"] == "pass", t["name"])),
        },
        "freshness": freshness,
        "models": [n for n in nodes if n["type"] == "model"],
        "timings": {k: round(v, 2) for k, v in timings.items()},
        "benchmark": universe.benchmark,
    }
    (SITE_DATA / "health.json").write_text(json.dumps(health, indent=1, default=str))


def _exists(con, table: str) -> bool:
    return con.execute("select count(*) from information_schema.tables where table_name = ?", [table]).fetchone()[0] > 0


def _export_data(con) -> None:
    # Every mart as Parquet (downloadable) and CSV (queried in the browser by DuckDB-WASM:
    # its CSV reader is built in, while Parquet support is an extension fetched from a CDN).
    for m in MARTS:
        con.execute(f"copy (select * from {m}) to '{SITE_DATA / (m + '.parquet')}' (format parquet, compression zstd)")
        con.execute(f"copy (select * from {m}) to '{SITE_DATA / (m + '.csv')}' (header, dateformat '%Y-%m-%d')")

    summary = _rows(con, "select * from mart_ticker_summary order by is_benchmark, ticker")

    # Daily series, columnar per ticker to keep the file small.
    series = {}
    for t in [r["ticker"] for r in summary]:
        rows = con.execute(
            """select trade_date, round(close, 2), round(adj_close, 3), round(ma_50, 3), round(ma_200, 3),
                      round(drawdown_252d, 4), round(growth_of_100, 3), round(volatility_63d, 4), volume
               from fct_daily_prices where ticker = ? order by trade_date""",
            [t],
        ).fetchall()
        cols = ["date", "close", "adj_close", "ma_50", "ma_200", "drawdown", "growth", "vol_63d", "volume"]
        series[t] = {c: [_clean(r[i], 6) for r in rows] for i, c in enumerate(cols)}

    data = {
        "summary": summary,
        "series": series,
        "correlation": _rows(con, "select * from mart_return_correlation order by ticker_a, ticker_b", 4),
        "revenue": _rows(con, "select * from fct_quarterly_revenue order by ticker, period_end"),
        "monthly": _rows(con, "select ticker, strftime(month, '%Y-%m') as month, monthly_return from mart_monthly_returns order by ticker, month", 4),
    }
    (SITE_DATA / "dashboard.json").write_text(json.dumps(data, separators=(",", ":"), default=str))
