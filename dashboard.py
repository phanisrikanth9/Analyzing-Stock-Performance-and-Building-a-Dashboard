"""Build the stock performance dashboard (index.html) for Tesla, Amazon, AMD and GameStop.

    python dashboard.py            # real data from Yahoo Finance (needs internet)
    python dashboard.py --demo     # synthetic prices, for working offline

A GitHub Action runs this every weekday after the US market closes and publishes
the page with GitHub Pages, so the dashboard stays current on its own.
"""
import argparse
import datetime as dt
import html
import json
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

TICKERS = {"TSLA": "Tesla", "AMZN": "Amazon", "AMD": "AMD", "GME": "GameStop"}
COLORS = {"TSLA": "#d6342c", "AMZN": "#e68a00", "AMD": "#1f6f5c", "GME": "#3653b0"}
TRADING_DAYS = 252
HERE = os.path.dirname(os.path.abspath(__file__))


# ------------------------------------------------------------------ data
def fetch_prices(years=5):
    import yfinance as yf
    raw = yf.download(list(TICKERS), period=f"{years}y", auto_adjust=True, progress=False, group_by="column")
    close = raw["Close"][list(TICKERS)].dropna(how="all")
    volume = raw["Volume"][list(TICKERS)].reindex(close.index)
    return close, volume


def fetch_revenue():
    """Quarterly total revenue (USD) from Yahoo Finance, most recent quarters only."""
    import yfinance as yf
    out = {}
    for t in TICKERS:
        try:
            stmt = yf.Ticker(t).quarterly_income_stmt
            if stmt is not None and "Total Revenue" in stmt.index:
                out[t] = stmt.loc["Total Revenue"].dropna().sort_index()
        except Exception as e:  # one failing ticker should not break the page
            print(f"revenue for {t} unavailable: {e}")
    return out


def demo_data(years=5, seed=7):
    """Geometric Brownian motion prices so the page can be built without internet."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range(end=dt.date.today(), periods=years * TRADING_DAYS)
    params = {"TSLA": (0.25, 0.60, 250), "AMZN": (0.12, 0.33, 150), "AMD": (0.20, 0.50, 110), "GME": (0.05, 0.90, 25)}
    close, volume = {}, {}
    for t, (mu, sigma, start) in params.items():
        r = rng.normal((mu - sigma ** 2 / 2) / TRADING_DAYS, sigma / np.sqrt(TRADING_DAYS), len(days))
        close[t] = start * np.exp(np.cumsum(r))
        volume[t] = rng.lognormal(16, 0.4, len(days))
    q = pd.date_range(end=dt.date.today(), periods=6, freq="QE")
    base = {"TSLA": 24e9, "AMZN": 150e9, "AMD": 6e9, "GME": 1.2e9}
    revenue = {t: pd.Series(b * (1 + 0.03 * np.arange(6)) * rng.uniform(0.92, 1.08, 6), index=q) for t, b in base.items()}
    return pd.DataFrame(close, index=days), pd.DataFrame(volume, index=days), revenue


# ------------------------------------------------------------------ metrics
def metrics(close):
    rows = []
    last = close.index[-1]
    year_ago = close.loc[: last - pd.Timedelta(days=365)].iloc[-1]
    ytd_start = close.loc[: pd.Timestamp(last.year, 1, 1) - pd.Timedelta(days=1)]
    ytd_base = ytd_start.iloc[-1] if len(ytd_start) else close.iloc[0]
    one_year = close.loc[last - pd.Timedelta(days=365):]
    rets = close.pct_change()
    for t in TICKERS:
        s = one_year[t].dropna()
        rows.append({
            "ticker": t, "name": TICKERS[t], "last": close[t].iloc[-1],
            "day": rets[t].iloc[-1],
            "ytd": close[t].iloc[-1] / ytd_base[t] - 1,
            "one_year": close[t].iloc[-1] / year_ago[t] - 1,
            "vol": rets[t].loc[s.index].std() * np.sqrt(TRADING_DAYS),
            "max_dd": (s / s.cummax() - 1).min(),
            "from_high": s.iloc[-1] / s.max() - 1,
        })
    return pd.DataFrame(rows).set_index("ticker")


def insights(m):
    best, worst = m["one_year"].idxmax(), m["one_year"].idxmin()
    calm, wild = m["vol"].idxmin(), m["vol"].idxmax()
    return [
        f"<b>{TICKERS[best]}</b> did best over the last 12 months ({m.loc[best, 'one_year']:+.0%}); "
        f"<b>{TICKERS[worst]}</b> did worst ({m.loc[worst, 'one_year']:+.0%}).",
        f"<b>{TICKERS[wild]}</b> is the most volatile ({m.loc[wild, 'vol']:.0%} a year), "
        f"<b>{TICKERS[calm]}</b> the calmest ({m.loc[calm, 'vol']:.0%}).",
        f"The deepest fall from a peak in the last year was <b>{TICKERS[m['max_dd'].idxmin()]}</b> "
        f"at {m['max_dd'].min():.0%}.",
    ]


# ------------------------------------------------------------------ figures
FONT = dict(family="IBM Plex Sans, Segoe UI, Arial, sans-serif", size=13, color="#22262c")
GRID = "#e6e8ec"


def _style(fig, height):
    fig.update_layout(template="plotly_white", font=FONT, height=height, margin=dict(l=56, r=20, t=40, b=40),
                      legend=dict(orientation="h", y=1.08, x=0), hovermode="x unified",
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    fig.update_xaxes(gridcolor=GRID, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig


def fig_performance(close):
    rebased = close / close.bfill().iloc[0] * 100
    fig = go.Figure()
    for t in TICKERS:
        fig.add_trace(go.Scatter(x=rebased.index, y=rebased[t], name=TICKERS[t], line=dict(color=COLORS[t], width=1.8),
                                 hovertemplate="%{y:.0f}"))
    fig.add_hline(y=100, line=dict(color="#8a9099", width=1, dash="dot"))
    ticks = [t for t in (5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000)
             if rebased.min().min() / 2 <= t <= rebased.max().max() * 2]
    fig.update_yaxes(type="log", title="Value of $100 invested (log scale)", tickvals=ticks,
                     ticktext=[f"${t:,}" for t in ticks], minor=dict(showgrid=False))
    fig.update_xaxes(rangeselector=dict(buttons=[dict(count=6, label="6M", step="month", stepmode="backward"),
                                                 dict(count=1, label="1Y", step="year", stepmode="backward"),
                                                 dict(count=3, label="3Y", step="year", stepmode="backward"),
                                                 dict(step="all", label="5Y")], x=0, y=1.02, yanchor="bottom"))
    fig = _style(fig, 460)
    fig.update_layout(legend=dict(orientation="h", y=1.02, yanchor="bottom", x=1, xanchor="right"), margin=dict(t=56))
    return fig


def fig_prices(close, volume):
    fig = make_subplots(rows=2, cols=2, subplot_titles=[f"{TICKERS[t]} ({t})" for t in TICKERS],
                        vertical_spacing=0.14, horizontal_spacing=0.08)
    recent = close.iloc[-2 * TRADING_DAYS:]
    for i, t in enumerate(TICKERS):
        r, c = i // 2 + 1, i % 2 + 1
        s = close[t]
        fig.add_trace(go.Scatter(x=recent.index, y=recent[t], name="Close", line=dict(color=COLORS[t], width=1.6),
                                 showlegend=False, hovertemplate="$%{y:.2f}"), r, c)
        for w, dash in ((50, "solid"), (200, "dot")):
            ma = s.rolling(w).mean().loc[recent.index]
            fig.add_trace(go.Scatter(x=recent.index, y=ma, name=f"{w}-day avg", line=dict(color="#6b717a", width=1, dash=dash),
                                     showlegend=(i == 0), legendgroup=str(w), hovertemplate="$%{y:.2f}"), r, c)
        fig.update_yaxes(tickprefix="$", row=r, col=c)
    fig = _style(fig, 640)
    fig.update_layout(legend=dict(orientation="h", y=-0.08, yanchor="top", x=0), margin=dict(t=40, b=60))
    return fig


def fig_drawdown(close):
    one_year = close.iloc[-TRADING_DAYS:]
    dd = one_year / one_year.cummax() - 1
    fig = go.Figure()
    for t in TICKERS:
        fig.add_trace(go.Scatter(x=dd.index, y=dd[t], name=TICKERS[t], line=dict(color=COLORS[t], width=1.4),
                                 hovertemplate="%{y:.0%}"))
    fig.update_yaxes(tickformat=".0%", title="Below previous peak")
    return _style(fig, 360)


def fig_revenue(revenue):
    if not revenue:
        return None
    fig = make_subplots(rows=1, cols=len(revenue), subplot_titles=[TICKERS[t] for t in revenue], horizontal_spacing=0.06)
    for i, (t, s) in enumerate(revenue.items(), start=1):
        labels = [f"Q{(d.month - 1) // 3 + 1} {d.year}" for d in s.index]
        fig.add_trace(go.Bar(x=labels, y=s.values / 1e9, marker_color=COLORS[t], showlegend=False,
                             hovertemplate="$%{y:.1f}B<extra></extra>"), 1, i)
        fig.update_yaxes(tickprefix="$", ticksuffix="B", row=1, col=i)
    fig = _style(fig, 340)
    fig.update_layout(hovermode="closest")
    return fig


def fig_correlation(close):
    corr = close.iloc[-TRADING_DAYS:].pct_change().corr().loc[list(TICKERS), list(TICKERS)]
    names = [TICKERS[t] for t in corr.index]
    fig = go.Figure(go.Heatmap(z=corr.values, x=names, y=names, zmin=-1, zmax=1, colorscale="RdBu", reversescale=True,
                               text=np.round(corr.values, 2), texttemplate="%{text}", hovertemplate="%{y} vs %{x}: %{z:.2f}<extra></extra>",
                               colorbar=dict(title="r", thickness=12)))
    fig = _style(fig, 380)
    fig.update_layout(hovermode="closest")
    return fig


# ------------------------------------------------------------------ page
def pct(x):
    cls = "up" if x > 0 else "down" if x < 0 else ""
    return f'<span class="{cls}">{x:+.1%}</span>'


def render(close, volume, revenue, demo=False):
    m = metrics(close)
    figs = {"perf": fig_performance(close), "prices": fig_prices(close, volume), "dd": fig_drawdown(close),
            "rev": fig_revenue(revenue), "corr": fig_correlation(close)}
    divs = {k: (f.to_html(full_html=False, include_plotlyjs=False, config={"displaylogo": False, "responsive": True})
                if f is not None else '<p class="muted">Revenue data was not available this run.</p>')
            for k, f in figs.items()}
    tiles = "".join(
        f'<div class="tile" style="--c:{COLORS[t]}"><div class="tk">{t}</div><div class="nm">{html.escape(TICKERS[t])}</div>'
        f'<div class="px">${r.last:,.2f}</div><div class="chg">{pct(r.day)} today</div>'
        f'<dl><dt>1 year</dt><dd>{pct(r.one_year)}</dd><dt>Year to date</dt><dd>{pct(r.ytd)}</dd></dl></div>'
        for t, r in m.iterrows())
    table = "".join(
        f"<tr><th>{html.escape(TICKERS[t])} <span class='muted'>{t}</span></th><td>${r.last:,.2f}</td><td>{pct(r.ytd)}</td>"
        f"<td>{pct(r.one_year)}</td><td>{r.vol:.0%}</td><td>{r.max_dd:.0%}</td><td>{r.from_high:.0%}</td></tr>"
        for t, r in m.iterrows())
    asof = close.index[-1].strftime("%B %-d, %Y")
    banner = '<div class="banner">Sample data: built with <code>--demo</code>, these are simulated prices.</div>' if demo else ""
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        page = f.read()
    for k, v in {"BANNER": banner, "ASOF": asof, "TILES": tiles, "INSIGHTS": "".join(f"<li>{s}</li>" for s in insights(m)),
                 "PERF": divs["perf"], "PRICES": divs["prices"], "DD": divs["dd"], "REV": divs["rev"],
                 "CORR": divs["corr"], "TABLE": table, "SOURCE": "simulated (demo)" if demo else "Yahoo Finance via yfinance"}.items():
        page = page.replace("{{" + k + "}}", v)
    return page, m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="use simulated prices (no internet needed)")
    ap.add_argument("--out", default=os.path.join(HERE, "index.html"))
    args = ap.parse_args()
    if args.demo:
        close, volume, revenue = demo_data()
    else:
        close, volume = fetch_prices()
        revenue = fetch_revenue()
    page, m = render(close, volume, revenue, demo=args.demo)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(page)
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    m.round(4).to_csv(os.path.join(HERE, "data", "latest_metrics.csv"))
    print(f"Wrote {args.out} (data to {close.index[-1].date()})")
    print(json.dumps(m.round(3).to_dict(orient="index"), indent=1, default=float))


if __name__ == "__main__":
    main()
