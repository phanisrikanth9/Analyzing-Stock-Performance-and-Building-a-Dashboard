# Stock Performance Dashboard

A self-updating dashboard for **Tesla, Amazon, AMD and GameStop**: returns, trend, drawdowns, quarterly revenue and how the four stocks move together.

**Live dashboard:** https://phanisrikanth9.github.io/Analyzing-Stock-Performance-and-Building-a-Dashboard/

![Dashboard preview (built with sample data)](docs/screenshot.png)

## What it shows

| Section | Question it answers |
|---|---|
| Ticker tiles | Where is each stock now, and how did it do today, this year and over 12 months? |
| What would $100 have become? | Which stock rewarded a long-term holder most (5 years, log scale, 6M / 1Y / 3Y / 5Y buttons)? |
| Price and trend | Is the stock above its 50-day and 200-day moving averages? |
| How far below the peak? | How deep were the falls in the last year (drawdown)? |
| Quarterly revenue | Is the business itself growing? |
| Do they move together? | Correlation of daily returns, useful for diversification |
| All figures | Year to date, 1-year return, annualised volatility, max drawdown, distance from 52-week high |

A short summary at the top is written automatically from the numbers (best and worst performer, most volatile, deepest drawdown).

## How it stays up to date

`.github/workflows/update-dashboard.yml` runs every weekday after the US market closes. It downloads fresh prices and revenue from Yahoo Finance with `yfinance`, rebuilds `index.html` with Plotly, and commits it. GitHub Pages serves that file, so the dashboard updates itself with no server.

## Run it locally

```bash
pip install -r requirements.txt
python dashboard.py          # real data, needs internet
python dashboard.py --demo   # simulated prices, works offline
```

Then open `index.html`. The latest figures are also saved to `data/latest_metrics.csv`.

## Methods

- Prices are adjusted for splits and dividends (`auto_adjust=True`).
- Volatility = standard deviation of daily returns × √252.
- Drawdown = price ÷ highest price so far in the window − 1.
- Correlation uses daily returns over the last 252 trading days.

## History

This started as the final assignment of IBM's *Python Project for Data Science* course (Coursera), which scraped Tesla and GameStop revenue tables with BeautifulSoup and plotted them. The original script is kept in [`course_project/ibm_assignment.py`](course_project/ibm_assignment.py). The rebuild adds Amazon and AMD, risk metrics, automated daily updates and a published dashboard.

Not investment advice. Built by [Phani Srikanth Samayam](https://phanisrikanth9.github.io/Phani-Portfolio/).
