-- More than 7 calendar days between two trading days means data went missing
-- (the longest US market closure in the window is a long weekend).
with gaps as (
    select ticker, trade_date,
           datediff('day', lag(trade_date) over (partition by ticker order by trade_date), trade_date) as gap_days
    from {{ ref('stg_prices') }}
)
select * from gaps where gap_days > 7
