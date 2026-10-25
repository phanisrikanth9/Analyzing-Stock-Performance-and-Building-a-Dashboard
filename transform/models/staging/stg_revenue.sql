select
    upper(trim(ticker))          as ticker,
    cast(period_end as date)     as period_end,
    cast(revenue as double)      as revenue
from {{ source('raw', 'revenue') }}
where revenue is not null
