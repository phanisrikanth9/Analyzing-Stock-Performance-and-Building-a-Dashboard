select symbol as ticker, name, sector, color, is_benchmark
from {{ ref('tickers') }}
