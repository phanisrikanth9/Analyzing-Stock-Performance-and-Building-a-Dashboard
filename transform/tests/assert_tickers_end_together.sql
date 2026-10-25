-- All tickers should be updated to the same latest trading day; one lagging behind
-- usually means its download failed silently.
{{ config(severity = 'warn') }}
with last as (select ticker, max(trade_date) as d from {{ ref('stg_prices') }} group by ticker)
select * from last where d < (select max(d) from last) - interval 3 day
