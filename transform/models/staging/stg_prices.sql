-- One row per ticker per trading day, typed and de-duplicated.
with src as (
    select
        upper(trim(ticker))           as ticker,
        cast(date as date)            as trade_date,
        cast(open as double)          as open,
        cast(high as double)          as high,
        cast(low as double)           as low,
        cast(close as double)         as close,
        cast(adj_close as double)     as adj_close,
        cast(volume as bigint)        as volume,
        coalesce(cast(dividend as double), 0)    as dividend,
        coalesce(cast(split_ratio as double), 0) as split_ratio
    from {{ source('raw', 'prices') }}
    where close is not null
)
select *
from src
qualify row_number() over (partition by ticker, trade_date order by trade_date) = 1
