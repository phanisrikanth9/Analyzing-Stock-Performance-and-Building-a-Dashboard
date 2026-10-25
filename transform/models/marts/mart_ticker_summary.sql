-- One row per ticker: the "scorecard" at the top of the dashboard.
{% set benchmark = var('benchmark') %}
with p as (select * from {{ ref('fct_daily_prices') }}),

last_day as (
    select ticker, max(trade_date) as as_of from p group by ticker
),

anchors as (
    -- Closing price on or before each look-back date (handles weekends and holidays).
    select
        l.ticker,
        l.as_of,
        (select adj_close from p p2 where p2.ticker = l.ticker and p2.trade_date <= make_date(year(l.as_of) - 1, 12, 31) order by trade_date desc limit 1) as px_prev_year_end,
        (select adj_close from p p2 where p2.ticker = l.ticker and p2.trade_date <= l.as_of - interval 1 year  order by trade_date desc limit 1) as px_1y,
        (select adj_close from p p2 where p2.ticker = l.ticker and p2.trade_date <= l.as_of - interval 3 year  order by trade_date desc limit 1) as px_3y
    from last_day l
),

last_year as (
    -- The peak for the 1-year drawdown is taken inside the window only (standard peak-to-trough).
    select p.*,
           p.adj_close / max(p.adj_close) over (partition by p.ticker order by p.trade_date) - 1 as dd_in_window
    from p join last_day l using (ticker)
    where p.trade_date > l.as_of - interval 1 year
),

risk as (
    select
        ticker,
        stddev_samp(daily_return) * sqrt(252)   as volatility_1y,
        min(dd_in_window)                       as max_drawdown_1y,
        max(adj_close)                          as high_52w,
        min(adj_close)                          as low_52w,
        avg(volume)                             as avg_volume_1y
    from last_year
    group by ticker
),

beta as (
    -- Beta and correlation against the benchmark over the last year of daily returns.
    select
        s.ticker,
        regr_slope(s.daily_return, b.daily_return) as beta_1y,
        corr(s.daily_return, b.daily_return)       as corr_benchmark_1y
    from last_year s
    join last_year b
      on b.trade_date = s.trade_date and b.ticker = '{{ benchmark }}'
    where s.daily_return is not null and b.daily_return is not null
    group by s.ticker
),

latest as (
    select p.* from p join last_day l on p.ticker = l.ticker and p.trade_date = l.as_of
)

select
    t.ticker,
    t.name,
    t.sector,
    t.color,
    t.is_benchmark,
    a.as_of,
    lt.close                                    as last_close,
    lt.adj_close                                as last_adj_close,
    lt.daily_return                             as day_return,
    lt.adj_close / a.px_prev_year_end - 1       as ytd_return,
    lt.adj_close / a.px_1y - 1                  as return_1y,
    power(lt.adj_close / a.px_3y, 1.0 / 3) - 1  as cagr_3y,
    r.volatility_1y,
    r.max_drawdown_1y,
    lt.adj_close / r.high_52w - 1               as from_52w_high,
    r.high_52w,
    r.low_52w,
    r.avg_volume_1y,
    lt.ma_50,
    lt.ma_200,
    lt.adj_close > lt.ma_50                     as above_ma_50,
    lt.adj_close > lt.ma_200                    as above_ma_200,
    b.beta_1y,
    b.corr_benchmark_1y,
    (lt.adj_close / a.px_1y - 1) / nullif(r.volatility_1y, 0) as return_per_risk_1y
from {{ ref('stg_tickers') }} t
join anchors a   on a.ticker = t.ticker
join latest lt   on lt.ticker = t.ticker
left join risk r on r.ticker = t.ticker
left join beta b on b.ticker = t.ticker
