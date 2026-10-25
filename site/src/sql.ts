// In-browser SQL over the published marts, with DuckDB compiled to WebAssembly.
// Loaded only when the visitor opens the console: the engine is ~8 MB compressed.

import type { AsyncDuckDB, AsyncDuckDBConnection } from '@duckdb/duckdb-wasm'

let ready: Promise<{ db: AsyncDuckDB; conn: AsyncDuckDBConnection }> | null = null

export const TABLES = ['fct_daily_prices', 'mart_ticker_summary', 'mart_return_correlation', 'fct_quarterly_revenue', 'mart_monthly_returns']

export function initDuckDB(dataUrl: string): Promise<{ db: AsyncDuckDB; conn: AsyncDuckDBConnection }> {
  if (ready) return ready
  ready = (async () => {
    const duckdb = await import('@duckdb/duckdb-wasm')
    const wasm = (await import('@duckdb/duckdb-wasm/dist/duckdb-eh.wasm?url')).default
    const worker = (await import('@duckdb/duckdb-wasm/dist/duckdb-browser-eh.worker.js?url')).default
    const db = new duckdb.AsyncDuckDB(new duckdb.VoidLogger(), new Worker(worker))
    await db.instantiate(wasm)
    const conn = await db.connect()
    for (const t of TABLES) {
      // CSV keeps the console self-contained: DuckDB-WASM's Parquet reader is an extension
      // downloaded from extensions.duckdb.org at runtime, its CSV reader is built in.
      const url = new URL(`${dataUrl}${t}.csv`, location.href).href
      await db.registerFileURL(`${t}.csv`, url, duckdb.DuckDBDataProtocol.HTTP, false)
      await conn.query(`create table ${t} as select * from read_csv('${t}.csv', header = true, auto_detect = true)`)
    }
    return { db, conn }
  })()
  ready.catch(() => (ready = null))
  return ready
}

export interface QueryResult {
  columns: string[]
  rows: unknown[][]
  ms: number
  truncated: boolean
}

export async function runQuery(dataUrl: string, sql: string, limit = 500): Promise<QueryResult> {
  const { conn } = await initDuckDB(dataUrl)
  const t0 = performance.now()
  const table = await conn.query(sql)
  const ms = performance.now() - t0
  const columns = table.schema.fields.map((f) => f.name)
  // Arrow returns DATE / TIMESTAMP values as epoch milliseconds.
  const isDate = table.schema.fields.map((f) => /^(Date|Timestamp)/i.test(String(f.type)))
  const rows: unknown[][] = []
  const n = Math.min(table.numRows, limit)
  for (let i = 0; i < n; i++) {
    const r = table.get(i)!
    rows.push(columns.map((c, j) => normalize((r as unknown as Record<string, unknown>)[c], isDate[j])))
  }
  return { columns, rows, ms, truncated: table.numRows > limit }
}

function normalize(v: unknown, isDate = false): unknown {
  if (isDate && (typeof v === 'number' || typeof v === 'bigint')) return new Date(Number(v)).toISOString().slice(0, 10)
  if (typeof v === 'bigint') return Number(v)
  if (v instanceof Date) return v.toISOString().slice(0, 10)
  return v
}

export const EXAMPLES: { label: string; sql: string }[] = [
  {
    label: 'Best and worst days',
    sql: `-- Each stock's biggest one-day gain and loss in the data
select ticker,
       max(daily_return) as best_day,
       arg_max(trade_date, daily_return) as best_date,
       min(daily_return) as worst_day,
       arg_min(trade_date, daily_return) as worst_date
from fct_daily_prices
group by ticker
order by ticker`,
  },
  {
    label: 'Golden crosses',
    sql: `-- Days the 50-day average crossed above the 200-day average
select ticker, trade_date, round(adj_close, 2) as price
from (
  select *, lag(ma_50 > ma_200) over (partition by ticker order by trade_date) as was_above
  from fct_daily_prices
  where ma_200 is not null
)
where ma_50 > ma_200 and not was_above
order by trade_date desc`,
  },
  {
    label: 'Yearly returns',
    sql: `-- Calendar-year total return per stock
select ticker, year(trade_date) as year,
       arg_max(adj_close, trade_date) / arg_min(adj_close, trade_date) - 1 as return
from fct_daily_prices
group by all
order by ticker, year`,
  },
  {
    label: 'Revenue growth',
    sql: `select ticker, quarter_label, revenue / 1e9 as revenue_bn, qoq_growth
from fct_quarterly_revenue
order by ticker, period_end`,
  },
]
