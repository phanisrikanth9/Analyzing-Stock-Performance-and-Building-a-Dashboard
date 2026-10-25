export interface Summary {
  ticker: string
  name: string
  sector: string
  color: string
  is_benchmark: boolean
  as_of: string
  last_close: number
  day_return: number | null
  ytd_return: number | null
  return_1y: number | null
  cagr_3y: number | null
  volatility_1y: number | null
  max_drawdown_1y: number | null
  from_52w_high: number | null
  high_52w: number | null
  low_52w: number | null
  ma_50: number | null
  ma_200: number | null
  above_ma_50: boolean | null
  above_ma_200: boolean | null
  beta_1y: number | null
  corr_benchmark_1y: number | null
  return_per_risk_1y: number | null
}

export interface Series {
  date: string[]
  close: number[]
  adj_close: number[]
  ma_50: (number | null)[]
  ma_200: (number | null)[]
  drawdown: number[]
  growth: number[]
  vol_63d: (number | null)[]
  volume: (number | null)[]
}

export interface Dashboard {
  summary: Summary[]
  series: Record<string, Series>
  correlation: { ticker_a: string; ticker_b: string; correlation: number; n_days: number }[]
  revenue: { ticker: string; period_end: string; quarter_label: string; revenue: number; qoq_growth: number | null; yoy_growth: number | null }[]
  monthly: { ticker: string; month: string; monthly_return: number }[]
}

export interface TestResult {
  name: string
  type: string
  status: string
  failures: number | null
  seconds: number
  message: string
}

export interface Health {
  generated_at: string
  status: 'ok' | 'failed'
  source: string
  as_of: string
  ingest: { ticker: string; mode: string; rows_before: number; rows_after: number; new_rows: number; last_date: string | null; error: string | null; notes: string[] }[]
  revenue_rows: number
  row_counts: Record<string, number>
  tests: { total: number; passed: number; warned: number; failed: number; details: TestResult[] }
  freshness: TestResult[]
  models: TestResult[]
  timings: Record<string, number>
  benchmark: string
}
