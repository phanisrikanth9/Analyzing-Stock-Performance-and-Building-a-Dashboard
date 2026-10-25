select
    ticker,
    period_end,
    'Q' || quarter(period_end) || ' ' || year(period_end)               as quarter_label,
    revenue,
    revenue / lag(revenue) over (partition by ticker order by period_end) - 1 as qoq_growth,
    -- year-over-year only when the quarter four periods back is really a year earlier
    case
        when datediff('day', lag(period_end, 4) over (partition by ticker order by period_end), period_end) between 350 and 380
        then revenue / lag(revenue, 4) over (partition by ticker order by period_end) - 1
    end                                                                 as yoy_growth
from {{ ref('stg_revenue') }}
