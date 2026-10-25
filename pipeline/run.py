"""Run the whole pipeline: ingest -> dbt build (models + data tests) -> export.

    python -m pipeline.run                    # production: Yahoo Finance
    python -m pipeline.run --source fixture   # offline: real snapshot from 2026-10-22
    python -m pipeline.run --skip-ingest      # re-run transforms on the current raw layer

Exits non-zero if any data test fails, so CI never publishes bad data:
the live dashboard keeps showing the last good build.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys
import time

from .config import DBT_DIR, RAW, ROOT, WAREHOUSE_DB, load_universe
from .export import export_site
from .ingest import run_ingest
from .sources import get_source


def write_ticker_seed(universe) -> None:
    path = DBT_DIR / "seeds" / "tickers.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["symbol", "name", "sector", "color", "is_benchmark"])
        for t in universe.tickers:
            w.writerow([t.symbol, t.name, t.sector, t.color, str(t.symbol == universe.benchmark).lower()])


def run_dbt(args: list[str], dbt_vars: dict) -> tuple[bool, list[dict]]:
    """Invoke dbt in-process and return (success, per-node results)."""
    from dbt.cli.main import dbtRunner

    os.environ["RAW_DIR"] = str(RAW)
    os.environ["WAREHOUSE_DB"] = str(WAREHOUSE_DB)
    cli = [*args, "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR), "--vars", json.dumps(dbt_vars)]
    res = dbtRunner().invoke(cli)
    nodes = []
    for r in getattr(res.result, "results", None) or []:
        node = getattr(r, "node", None)
        nodes.append(
            {
                "name": getattr(node, "name", str(r)),
                "type": getattr(node, "resource_type", "source").__str__().split(".")[-1].lower(),
                "status": str(r.status).split(".")[-1].lower(),
                "failures": getattr(r, "failures", None),
                "seconds": round(getattr(r, "execution_time", 0) or 0, 3),
                "message": (getattr(r, "message", None) or "")[:300],
            }
        )
    return bool(res.success), nodes


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=["yahoo", "fixture"], default="yahoo")
    ap.add_argument("--skip-ingest", action="store_true")
    ap.add_argument("--as-of", type=dt.date.fromisoformat, help="pretend today is this date (fixture runs, backfills)")
    args = ap.parse_args(argv)

    universe = load_universe()
    timings: dict[str, float] = {}
    source = get_source(args.source)
    as_of = args.as_of or (dt.date(2026, 10, 22) if args.source == "fixture" else dt.date.today())

    write_ticker_seed(universe)
    t0 = time.perf_counter()
    if args.skip_ingest:
        manifest = json.loads((RAW / "_manifest.json").read_text())
    else:
        print(f"[1/3] ingest from {source.name} (as of {as_of})")
        manifest = run_ingest(source, universe, as_of)
        if all(p["mode"] == "failed" for p in manifest["prices"]):
            print("every ticker failed to download; stopping", file=sys.stderr)
            return 2
    timings["ingest"] = time.perf_counter() - t0

    print("[2/3] dbt build: seeds, models, data tests")
    t0 = time.perf_counter()
    dbt_vars = {"benchmark": universe.benchmark, "allow_missing_tickers": args.source == "fixture"}
    ok, nodes = run_dbt(["build"], dbt_vars)
    freshness: list[dict] = []
    if args.source == "yahoo":
        _, freshness = run_dbt(["source", "freshness"], dbt_vars)
    timings["transform"] = time.perf_counter() - t0

    print("[3/3] export marts for the dashboard")
    t0 = time.perf_counter()
    export_site(manifest, nodes, freshness, ok, timings, universe)
    timings["export"] = time.perf_counter() - t0

    failed = [n for n in nodes if n["status"] in ("fail", "error")]
    warned = [n for n in nodes if n["status"] == "warn"]
    tests = [n for n in nodes if n["type"] == "test"]
    print(f"done: {len(tests)} tests, {len(failed)} failed, {len(warned)} warnings "
          f"({', '.join(f'{k} {v:.1f}s' for k, v in timings.items())})")
    for n in failed + warned:
        print(f"  {n['status'].upper():5} {n['name']}: {n['message']}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
