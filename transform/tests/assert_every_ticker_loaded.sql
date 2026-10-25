-- Every ticker in config/tickers.yml must have prices, unless explicitly allowed (offline fixture).
{{ config(severity = 'warn' if var('allow_missing_tickers') else 'error') }}
select t.ticker
from {{ ref('stg_tickers') }} t
left join (select distinct ticker from {{ ref('stg_prices') }}) p using (ticker)
where p.ticker is null
