-- Pairwise correlation of daily returns over the last 252 shared trading days.
with p as (select ticker, trade_date, daily_return from {{ ref('fct_daily_prices') }} where daily_return is not null),

recent_days as (
    select trade_date from (select distinct trade_date from p) order by trade_date desc limit 252
)

select
    a.ticker                                as ticker_a,
    b.ticker                                as ticker_b,
    corr(a.daily_return, b.daily_return)    as correlation,
    count(*)                                as n_days
from p a
join p b on a.trade_date = b.trade_date
where a.trade_date in (select trade_date from recent_days)
group by 1, 2
