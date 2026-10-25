"""Ingest behaviour: backfill, idempotency, incremental loads, restatements, failures."""
import datetime as dt

import pandas as pd
import pytest

from pipeline.ingest import detect_restatement, ingest_prices, read_raw, upsert
from pipeline.sources import PRICE_COLUMNS

TODAY = dt.date(2026, 10, 22)


class FakeSource:
    """Business-day prices with a controllable price level, to simulate restatements."""

    name = "fake"

    def __init__(self, scale=1.0, last=TODAY, fail=False):
        self.scale, self.last, self.fail, self.calls = scale, last, fail, []

    def prices(self, ticker, start, end):
        self.calls.append((start, end))
        if self.fail:
            raise ConnectionError("network down")
        days = pd.bdate_range(start, min(end, self.last))
        # Price depends only on the date, so overlapping requests agree.
        px = [self.scale * (100 + (d - pd.Timestamp("2020-01-01")).days * 0.1) for d in days]
        return pd.DataFrame({
            "ticker": ticker, "date": days.date, "open": px, "high": px, "low": px, "close": px, "adj_close": px,
            "volume": 1000, "dividend": 0.0, "split_ratio": 0.0,
        })[PRICE_COLUMNS]

    def revenue(self, ticker):
        return pd.DataFrame(columns=["ticker", "period_end", "revenue"])


def raw(tmp_path):
    return read_raw(tmp_path / "prices" / "TEST.parquet", PRICE_COLUMNS)


def test_first_run_backfills_history(tmp_path):
    r = ingest_prices(FakeSource(), "TEST", TODAY, 2, tmp_path)
    assert r.mode == "backfill"
    df = raw(tmp_path)
    assert len(df) == r.rows_after > 500
    assert str(df["date"].max()) == "2026-10-22"


def test_rerun_same_day_is_idempotent(tmp_path):
    src = FakeSource()
    ingest_prices(src, "TEST", TODAY, 2, tmp_path)
    before = raw(tmp_path)
    r = ingest_prices(src, "TEST", TODAY, 2, tmp_path)
    assert r.mode == "unchanged" and r.new_rows == 0
    pd.testing.assert_frame_equal(before, raw(tmp_path))


def test_next_day_fetches_only_a_small_window(tmp_path):
    ingest_prices(FakeSource(last=TODAY), "TEST", TODAY, 2, tmp_path)
    src = FakeSource(last=TODAY + dt.timedelta(days=1))
    r = ingest_prices(src, "TEST", TODAY + dt.timedelta(days=1), 2, tmp_path)
    assert r.mode == "incremental" and r.new_rows == 1
    start, _ = src.calls[0]
    assert (TODAY - start).days <= 7  # overlap window, not full history


def test_restatement_triggers_full_reload(tmp_path):
    ingest_prices(FakeSource(scale=1.0), "TEST", TODAY, 2, tmp_path)
    # A 2-for-1 split upstream halves every historical price.
    r = ingest_prices(FakeSource(scale=0.5), "TEST", TODAY, 2, tmp_path)
    assert r.mode == "reload"
    df = raw(tmp_path)
    assert df["close"].iloc[0] == pytest.approx(FakeSource(scale=0.5).prices("TEST", df["date"].iloc[0], df["date"].iloc[0])["close"].iloc[0])


def test_failure_keeps_existing_data(tmp_path):
    ingest_prices(FakeSource(), "TEST", TODAY, 2, tmp_path)
    before = raw(tmp_path)
    r = ingest_prices(FakeSource(fail=True), "TEST", TODAY, 2, tmp_path)
    assert r.mode == "failed" and "network down" in r.error
    pd.testing.assert_frame_equal(before, raw(tmp_path))
    assert not list(tmp_path.rglob("*.tmp"))


def test_upsert_prefers_new_rows():
    a = pd.DataFrame({"k": [1, 2], "v": ["old", "old"]})
    b = pd.DataFrame({"k": [2, 3], "v": ["new", "new"]})
    assert upsert(a, b, ["k"]).to_dict("list") == {"k": [1, 2, 3], "v": ["old", "new", "new"]}


def test_detect_restatement_ignores_tiny_float_noise():
    base = FakeSource().prices("T", TODAY - dt.timedelta(days=10), TODAY)
    noisy = base.copy()
    noisy["close"] *= 1 + 1e-7
    assert not detect_restatement(base, noisy)
    noisy["adj_close"] *= 0.997  # a dividend re-basing
    assert detect_restatement(base, noisy)
