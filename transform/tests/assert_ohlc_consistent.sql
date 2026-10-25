-- A day's low can't be above its close or high, and its high can't be below its open.
select ticker, trade_date, open, high, low, close
from {{ ref('stg_prices') }}
where low > least(open, close) * 1.0001
   or high < greatest(open, close) * 0.9999
