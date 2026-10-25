-- Total-return series: adj_close includes dividends, so returns are what a holder earned.
select
    ticker,
    trade_date,
    close,
    adj_close,
    volume,
    adj_close / lag(adj_close) over w - 1          as daily_return,
    ln(adj_close / lag(adj_close) over w)          as log_return,
    row_number() over w                            as day_index
from {{ ref('stg_prices') }}
window w as (partition by ticker order by trade_date)
