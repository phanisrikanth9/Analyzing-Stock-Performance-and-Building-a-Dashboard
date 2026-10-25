-- Daily fact table: price, trend, risk and drawdown per ticker.
-- Window statistics are left null until enough history exists (e.g. ma_200 needs 200 days).
with r as (select * from {{ ref('int_daily_returns') }}),

w as (
    select
        *,
        avg(adj_close)  over (partition by ticker order by trade_date rows between 49 preceding and current row)  as ma_50_raw,
        avg(adj_close)  over (partition by ticker order by trade_date rows between 199 preceding and current row) as ma_200_raw,
        max(adj_close)  over (partition by ticker order by trade_date rows between 251 preceding and current row) as high_252d,
        stddev_samp(daily_return) over (partition by ticker order by trade_date rows between 62 preceding and current row) as sd_63d,
        first_value(adj_close) over (partition by ticker order by trade_date)                                     as first_adj_close
    from r
)

select
    ticker,
    trade_date,
    close,
    adj_close,
    volume,
    daily_return,
    log_return,
    case when day_index >= 50  then ma_50_raw  end                       as ma_50,
    case when day_index >= 200 then ma_200_raw end                       as ma_200,
    adj_close / high_252d - 1                                            as drawdown_252d,
    case when day_index >= 64 then sd_63d * sqrt(252) end                as volatility_63d,
    100 * adj_close / first_adj_close                                    as growth_of_100
from w
