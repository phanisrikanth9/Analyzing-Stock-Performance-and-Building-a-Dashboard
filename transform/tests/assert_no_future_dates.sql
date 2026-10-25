select ticker, trade_date
from {{ ref('stg_prices') }}
where trade_date > current_date
