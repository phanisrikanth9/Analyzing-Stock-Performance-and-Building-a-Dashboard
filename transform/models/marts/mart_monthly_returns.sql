-- Calendar-month total returns, for the heatmap.
with month_end as (
    select ticker, date_trunc('month', trade_date) as month, arg_max(adj_close, trade_date) as px
    from {{ ref('fct_daily_prices') }}
    group by 1, 2
)
select
    ticker,
    month,
    px / lag(px) over (partition by ticker order by month) - 1 as monthly_return
from month_end
qualify lag(px) over (partition by ticker order by month) is not null
