"""End to end on the real 2026-10-22 snapshot: the SQL marts must reproduce the
figures the previous pandas version of this project published that day."""
import json

import pandas as pd
import pytest

from pipeline.config import FIXTURES, SITE_DATA
from pipeline.run import main


@pytest.fixture(scope="module")
def summary():
    assert main(["--source", "fixture"]) == 0
    data = json.loads((SITE_DATA / "dashboard.json").read_text())
    return {r["ticker"]: r for r in data["summary"]}


@pytest.mark.parametrize("col,ours", [
    ("ytd", "ytd_return"), ("one_year", "return_1y"), ("vol", "volatility_1y"),
    ("max_dd", "max_drawdown_1y"), ("from_high", "from_52w_high"), ("last", "last_close"),
])
def test_matches_previous_pandas_implementation(summary, col, ours):
    v1 = pd.read_csv(FIXTURES / "pandas_v1_metrics_2026-10-22.csv").set_index("ticker")
    # v1 dropped the first daily return inside the 1-year window; v2 keeps it.
    # One extra observation out of ~250 moves volatility by under 0.1 percentage point.
    tol = 1e-3 if col == "vol" else 6e-4
    for t, row in v1.iterrows():
        assert summary[t][ours] == pytest.approx(row[col], abs=tol), f"{t} {ours}"


def test_health_report_is_written(summary):
    h = json.loads((SITE_DATA / "health.json").read_text())
    assert h["status"] == "ok"
    assert h["tests"]["failed"] == 0 and h["tests"]["total"] >= 25
    assert h["row_counts"]["fct_daily_prices"] == 4 * 1254
