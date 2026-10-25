import Plotly from 'plotly.js-cartesian-dist-min'
import './style.css'
import type { Dashboard, Health, Summary } from './types'
import { EXAMPLES, runQuery } from './sql'

const DATA = `${import.meta.env.BASE_URL}data/`
const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T

const pct = (v: number | null | undefined, d = 1) => (v == null ? '–' : `${v >= 0 ? '+' : ''}${(v * 100).toFixed(d)}%`)
const pctPlain = (v: number | null | undefined, d = 1) => (v == null ? '–' : `${(v * 100).toFixed(d)}%`)
const money = (v: number | null | undefined) => (v == null ? '–' : `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`)
const num = (v: number | null | undefined, d = 2) => (v == null ? '–' : v.toFixed(d))
const cls = (v: number | null | undefined) => (v == null ? '' : v >= 0 ? 'up' : 'down')
const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]!)

const BASE_LAYOUT: Partial<Plotly.Layout> = {
  margin: { l: 52, r: 16, t: 10, b: 36 },
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(0,0,0,0)',
  font: { family: 'Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif', size: 12, color: '#334155' },
  xaxis: { gridcolor: '#eef2f6', linecolor: '#cbd5e1', zeroline: false },
  yaxis: { gridcolor: '#eef2f6', linecolor: '#cbd5e1', zeroline: false },
  legend: { orientation: 'h', y: 1.1, x: 0 },
  hovermode: 'x unified',
}
// Plotly writes auto-detected axis types back into the layout object it is given, so every
// chart needs its own copy; a shared object made later charts inherit a 'date' x-axis.
const layout = (): Partial<Plotly.Layout> => structuredClone(BASE_LAYOUT)
const CONFIG: Partial<Plotly.Config> = { displayModeBar: false, responsive: true }

async function main() {
  const [dash, health] = await Promise.all([
    fetch(`${DATA}dashboard.json`).then((r) => r.json() as Promise<Dashboard>),
    fetch(`${DATA}health.json`).then((r) => r.json() as Promise<Health>),
  ])
  const color = Object.fromEntries(dash.summary.map((s) => [s.ticker, s.color]))
  const stocks = dash.summary.filter((s) => !s.is_benchmark)
  const bench = dash.summary.find((s) => s.is_benchmark)

  $('asof').textContent = `Prices as of ${fmtDate(dash.summary[0]?.as_of)} · updated automatically every weekday`
  renderHealthPill(health)
  renderStory(stocks, bench)
  renderCards(dash.summary)
  renderGrowth(dash, color, 12)
  document.querySelectorAll<HTMLButtonElement>('#rangeBtns button').forEach((b) =>
    b.addEventListener('click', () => {
      document.querySelectorAll('#rangeBtns button').forEach((x) => x.classList.toggle('on', x === b))
      renderGrowth(dash, color, Number(b.dataset.r))
    }),
  )
  fillSelect('trendTicker', stocks, (t) => renderTrend(dash, t, color[t]))
  renderTrend(dash, stocks[0].ticker, color[stocks[0].ticker])
  renderDrawdown(dash, color)
  renderRisk(dash.summary)
  renderCorrelation(dash)
  fillSelect('monthTicker', dash.summary, (t) => renderMonthly(dash, t))
  renderMonthly(dash, stocks[0].ticker)
  renderRevenue(dash, color)
  renderTable(dash.summary)
  renderPipeline(health)
  setupSql()
}

function fmtDate(iso?: string) {
  if (!iso) return '–'
  return new Date(`${iso}T12:00:00`).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
}

function fillSelect(id: string, rows: Summary[], onChange: (t: string) => void) {
  const sel = $<HTMLSelectElement>(id)
  sel.innerHTML = rows.map((s) => `<option value="${s.ticker}">${esc(s.name)} (${s.ticker})</option>`).join('')
  sel.addEventListener('change', () => onChange(sel.value))
}

function renderHealthPill(h: Health) {
  const pill = $('healthPill')
  const ok = h.status === 'ok' && h.tests.failed === 0
  pill.classList.add(ok ? 'ok' : 'bad')
  pill.textContent = ok
    ? `✓ ${h.tests.passed}/${h.tests.total} data tests passed${h.tests.warned ? ` · ${h.tests.warned} warning` : ''}`
    : `✕ ${h.tests.failed} data test${h.tests.failed === 1 ? '' : 's'} failed · showing last good data`
}

/** A few sentences written from the numbers, so the page says something, not just shows it. */
function renderStory(stocks: Summary[], bench?: Summary) {
  const by = (k: keyof Summary) => [...stocks].filter((s) => s[k] != null).sort((a, b) => (b[k] as number) - (a[k] as number))
  const best = by('return_1y')[0]
  const worst = by('return_1y').at(-1)!
  const wild = by('volatility_1y')[0]
  const deep = [...stocks].sort((a, b) => (a.max_drawdown_1y ?? 0) - (b.max_drawdown_1y ?? 0))[0]
  const trend = stocks.filter((s) => s.above_ma_200).map((s) => s.name)
  const parts = [
    `Over the last 12 months <b>${esc(best.name)}</b> led with <span class="${cls(best.return_1y)}">${pct(best.return_1y)}</span>, while <b>${esc(worst.name)}</b> returned <span class="${cls(worst.return_1y)}">${pct(worst.return_1y)}</span>${bench ? ` (the S&amp;P 500: <span class="${cls(bench.return_1y)}">${pct(bench.return_1y)}</span>)` : ''}.`,
    `${esc(wild.name)} was the most volatile (${pctPlain(wild.volatility_1y, 0)} a year), and ${esc(deep.name)} had the deepest fall from a peak (${pctPlain(deep.max_drawdown_1y, 0)}).`,
    trend.length ? `${trend.join(trend.length === 2 ? ' and ' : ', ')} ${trend.length === 1 ? 'is' : 'are'} above the 200-day average.` : 'None of the four is above its 200-day average.',
  ]
  $('story').innerHTML = parts.join(' ')
}

function renderCards(rows: Summary[]) {
  $('cards').innerHTML = rows
    .map(
      (s) => `
    <article class="card ${s.is_benchmark ? 'bench' : ''}" style="--c:${s.color}">
      <header><span class="tk">${s.ticker}</span><span class="nm">${esc(s.name)}</span></header>
      <div class="px">${money(s.last_close)} <span class="${cls(s.day_return)}">${pct(s.day_return, 2)}</span></div>
      <dl>
        <div><dt>YTD</dt><dd class="${cls(s.ytd_return)}">${pct(s.ytd_return)}</dd></div>
        <div><dt>1 year</dt><dd class="${cls(s.return_1y)}">${pct(s.return_1y)}</dd></div>
        <div><dt>Volatility</dt><dd>${pctPlain(s.volatility_1y, 0)}</dd></div>
        <div><dt>${s.is_benchmark ? 'From high' : 'Beta'}</dt><dd>${s.is_benchmark ? pct(s.from_52w_high) : num(s.beta_1y)}</dd></div>
      </dl>
      <footer>${s.above_ma_200 == null ? '' : s.above_ma_200 ? '<span class="tag up">Uptrend</span>' : '<span class="tag down">Below 200-day</span>'}</footer>
    </article>`,
    )
    .join('')
}

function sliceMonths(dates: string[], months: number) {
  const last = new Date(`${dates[dates.length - 1]}T00:00:00`)
  const start = new Date(last)
  start.setMonth(start.getMonth() - months)
  const iso = start.toISOString().slice(0, 10)
  const i = dates.findIndex((d) => d >= iso)
  return i < 0 ? 0 : i
}

function renderGrowth(dash: Dashboard, color: Record<string, string>, months: number) {
  const traces = dash.summary.map((s) => {
    const se = dash.series[s.ticker]
    const i0 = sliceMonths(se.date, months)
    const base = se.adj_close[i0]
    return {
      x: se.date.slice(i0),
      y: se.adj_close.slice(i0).map((v) => (100 * v) / base),
      name: s.ticker,
      type: 'scatter',
      mode: 'lines',
      line: { color: color[s.ticker], width: s.is_benchmark ? 1.5 : 2, dash: s.is_benchmark ? 'dot' : 'solid' },
      hovertemplate: '$%{y:.0f}',
    } as Plotly.Data
  })
  Plotly.react('growthChart', traces, { ...layout(), yaxis: { ...layout().yaxis, type: months > 12 ? 'log' : 'linear', tickprefix: '$' } }, CONFIG)
}

function renderTrend(dash: Dashboard, t: string, c: string) {
  const se = dash.series[t]
  const i0 = sliceMonths(se.date, 24)
  const x = se.date.slice(i0)
  Plotly.react(
    'trendChart',
    [
      { x, y: se.close.slice(i0), name: 'Close', type: 'scatter', mode: 'lines', line: { color: c, width: 2 }, hovertemplate: '$%{y:.2f}' },
      // Moving averages are computed on adjusted prices; scale them to the close for display.
      { x, y: scaleToClose(se, 'ma_50', i0), name: '50-day', type: 'scatter', mode: 'lines', line: { color: '#64748b', width: 1.3 }, hovertemplate: '$%{y:.2f}' },
      { x, y: scaleToClose(se, 'ma_200', i0), name: '200-day', type: 'scatter', mode: 'lines', line: { color: '#0f172a', width: 1.3, dash: 'dash' }, hovertemplate: '$%{y:.2f}' },
    ],
    { ...layout(), yaxis: { ...layout().yaxis, tickprefix: '$' } },
    CONFIG,
  )
}

function scaleToClose(se: Dashboard['series'][string], key: 'ma_50' | 'ma_200', i0: number) {
  return se[key].slice(i0).map((v, i) => (v == null ? null : (v * se.close[i0 + i]) / se.adj_close[i0 + i]))
}

function renderDrawdown(dash: Dashboard, color: Record<string, string>) {
  const traces = dash.summary
    .filter((s) => !s.is_benchmark)
    .map((s) => {
      const se = dash.series[s.ticker]
      const i0 = sliceMonths(se.date, 12)
      return {
        x: se.date.slice(i0),
        y: se.drawdown.slice(i0),
        name: s.ticker,
        type: 'scatter',
        mode: 'lines',
        line: { color: color[s.ticker], width: 1.6 },
        hovertemplate: '%{y:.0%}',
      } as Plotly.Data
    })
  Plotly.react('ddChart', traces, { ...layout(), yaxis: { ...layout().yaxis, tickformat: '.0%' } }, CONFIG)
}

function renderRisk(rows: Summary[]) {
  const r = rows.filter((s) => s.volatility_1y != null && s.return_1y != null)
  Plotly.react(
    'riskChart',
    [
      {
        x: r.map((s) => s.volatility_1y),
        y: r.map((s) => s.return_1y),
        text: r.map((s) => s.ticker),
        type: 'scatter',
        mode: 'text+markers',
        textposition: 'top center',
        marker: { size: 16, color: r.map((s) => s.color), line: { color: '#fff', width: 2 } },
        hovertemplate: '%{text}<br>Volatility %{x:.0%}<br>Return %{y:.0%}<extra></extra>',
      } as Plotly.Data,
    ],
    {
      ...layout(),
      hovermode: 'closest',
      xaxis: { ...layout().xaxis, title: { text: 'Volatility (annualised)' }, tickformat: '.0%', range: [0, Math.max(...r.map((s) => s.volatility_1y!)) * 1.18] },
      yaxis: { ...layout().yaxis, title: { text: '12-month return' }, tickformat: '.0%', zeroline: true, zerolinecolor: '#cbd5e1', range: padRange(r.map((s) => s.return_1y!)) },
      margin: { ...layout().margin, l: 60, b: 48 },
    },
    CONFIG,
  )
}

function padRange(vals: number[]): [number, number] {
  const lo = Math.min(0, ...vals)
  const hi = Math.max(0, ...vals)
  const pad = (hi - lo) * 0.18 || 0.1
  return [lo - pad, hi + pad]
}

function renderCorrelation(dash: Dashboard) {
  const tickers = dash.summary.map((s) => s.ticker)
  const get = (a: string, b: string) => dash.correlation.find((c) => c.ticker_a === a && c.ticker_b === b)?.correlation ?? null
  const z = tickers.map((a) => tickers.map((b) => get(a, b)))
  Plotly.react(
    'corrChart',
    [
      {
        z,
        x: tickers,
        y: tickers,
        type: 'heatmap',
        zmin: -1,
        zmax: 1,
        colorscale: [
          [0, '#b91c1c'],
          [0.5, '#f8fafc'],
          [1, '#1d4ed8'],
        ],
        text: z.map((row) => row.map((v) => (v == null ? '' : v.toFixed(2)))) as unknown as string[],
        texttemplate: '%{text}',
        hovertemplate: '%{y} vs %{x}: %{z:.2f}<extra></extra>',
        colorbar: { thickness: 10 },
      } as Plotly.Data,
    ],
    { ...layout(), hovermode: 'closest', yaxis: { autorange: 'reversed' }, margin: { l: 52, r: 10, t: 10, b: 36 } },
    CONFIG,
  )
}

function renderMonthly(dash: Dashboard, t: string) {
  const rows = dash.monthly.filter((m) => m.ticker === t)
  const years = [...new Set(rows.map((r) => r.month.slice(0, 4)))].sort()
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  const z = years.map((y) => months.map((_, i) => rows.find((r) => r.month === `${y}-${String(i + 1).padStart(2, '0')}`)?.monthly_return ?? null))
  const lim = Math.max(0.15, ...rows.map((r) => Math.abs(r.monthly_return)))
  Plotly.react(
    'monthChart',
    [
      {
        z,
        x: months,
        y: years,
        type: 'heatmap',
        zmin: -lim,
        zmax: lim,
        colorscale: [
          [0, '#b91c1c'],
          [0.5, '#f8fafc'],
          [1, '#15803d'],
        ],
        text: z.map((row) => row.map((v) => (v == null ? '' : `${(v * 100).toFixed(0)}%`))) as unknown as string[],
        texttemplate: '%{text}',
        hovertemplate: '%{x} %{y}: %{z:.1%}<extra></extra>',
        showscale: false,
        xgap: 2,
        ygap: 2,
      } as Plotly.Data,
    ],
    { ...layout(), hovermode: 'closest', yaxis: { type: 'category' }, margin: { l: 52, r: 10, t: 6, b: 30 } },
    CONFIG,
  )
}

function renderRevenue(dash: Dashboard, color: Record<string, string>) {
  const tickers = [...new Set(dash.revenue.map((r) => r.ticker))]
  const traces = tickers.map((t) => {
    const rows = dash.revenue.filter((r) => r.ticker === t)
    return {
      x: rows.map((r) => r.quarter_label),
      y: rows.map((r) => r.revenue / 1e9),
      name: t,
      type: 'bar',
      marker: { color: color[t] },
      customdata: rows.map((r) => (r.qoq_growth == null ? '' : ` (${pct(r.qoq_growth)} vs prior quarter)`)),
      hovertemplate: `${t}: $%{y:.1f}B%{customdata}<extra></extra>`,
    } as Plotly.Data
  })
  Plotly.react(
    'revChart',
    traces,
    {
      ...layout(),
      barmode: 'group',
      hovermode: 'closest',
      yaxis: { ...layout().yaxis, type: 'log', tickprefix: '$', ticksuffix: 'B', title: { text: 'log scale' } },
      xaxis: { ...layout().xaxis, categoryorder: 'array', categoryarray: sortQuarters(dash.revenue.map((r) => r.quarter_label)) },
    },
    CONFIG,
  )
}

function sortQuarters(labels: string[]) {
  return [...new Set(labels)].sort((a, b) => {
    const [qa, ya] = a.split(' ')
    const [qb, yb] = b.split(' ')
    return Number(ya) - Number(yb) || qa.localeCompare(qb)
  })
}

function renderTable(rows: Summary[]) {
  const cols: [string, (s: Summary) => string][] = [
    ['Stock', (s) => `<b>${s.ticker}</b> <span class="muted">${esc(s.name)}</span>`],
    ['Last', (s) => money(s.last_close)],
    ['YTD', (s) => `<span class="${cls(s.ytd_return)}">${pct(s.ytd_return)}</span>`],
    ['1 year', (s) => `<span class="${cls(s.return_1y)}">${pct(s.return_1y)}</span>`],
    ['3-yr CAGR', (s) => `<span class="${cls(s.cagr_3y)}">${pct(s.cagr_3y)}</span>`],
    ['Volatility', (s) => pctPlain(s.volatility_1y)],
    ['Max drawdown', (s) => pctPlain(s.max_drawdown_1y)],
    ['From 52w high', (s) => pct(s.from_52w_high)],
    ['Beta', (s) => num(s.beta_1y)],
    ['Return / risk', (s) => num(s.return_per_risk_1y)],
  ]
  $('figures').innerHTML =
    `<thead><tr>${cols.map(([h]) => `<th>${h}</th>`).join('')}</tr></thead>` +
    `<tbody>${rows.map((s) => `<tr>${cols.map(([, f]) => `<td>${f(s)}</td>`).join('')}</tr>`).join('')}</tbody>`
}

function renderPipeline(h: Health) {
  const facts: [string, string][] = [
    ['Status', h.status === 'ok' ? '<span class="up">Passed, published</span>' : '<span class="down">Failed, not published</span>'],
    ['Ran at', new Date(h.generated_at).toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' })],
    ['Source', h.source === 'yahoo' ? 'Yahoo Finance (yfinance)' : 'Offline snapshot (fixture)'],
    ['Rows in marts', Object.entries(h.row_counts).map(([k, v]) => `${k}: ${v.toLocaleString()}`).join('<br>')],
    ['Step times', Object.entries(h.timings).map(([k, v]) => `${k} ${v}s`).join(' · ')],
  ]
  $('runFacts').innerHTML = facts.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join('')
  $('ingestTable').innerHTML =
    '<thead><tr><th>Ticker</th><th>Mode</th><th>Rows</th><th>New</th><th>Last day</th></tr></thead><tbody>' +
    h.ingest
      .map(
        (r) =>
          `<tr title="${esc(r.error || r.notes.join('; '))}"><td>${r.ticker}</td><td><span class="mode ${r.mode}">${r.mode}</span></td><td>${r.rows_after.toLocaleString()}</td><td>${r.new_rows}</td><td>${r.last_date ?? '–'}</td></tr>`,
      )
      .join('') +
    '</tbody>'
  $('testsSummary').textContent = `Data tests: ${h.tests.passed} passed, ${h.tests.warned} warnings, ${h.tests.failed} failed (show all)`
  $('flowTests').textContent = `${h.tests.total} dbt data tests: uniqueness, valid ranges, OHLC consistency, no missing weeks, every ticker loaded, freshness.`
  $('testList').innerHTML = h.tests.details
    .map((t) => `<li class="${t.status}"><span class="st">${t.status}</span><code>${esc(t.name)}</code>${t.status !== 'pass' ? `<span class="muted"> ${esc(t.message)}</span>` : ''}</li>`)
    .join('')
}

function setupSql() {
  const input = $<HTMLTextAreaElement>('sqlInput')
  const status = $('sqlStatus')
  const out = $('sqlResult')
  input.value = EXAMPLES[0].sql
  $('examples').innerHTML = EXAMPLES.map((e, i) => `<button data-i="${i}">${esc(e.label)}</button>`).join('')
  $('examples').addEventListener('click', (e) => {
    const b = (e.target as HTMLElement).closest('button')
    if (!b) return
    input.value = EXAMPLES[Number(b.dataset.i)].sql
    void run()
  })
  const run = async () => {
    status.textContent = 'Running… (loading DuckDB the first time)'
    $('runSql').setAttribute('disabled', '')
    try {
      const r = await runQuery(DATA, input.value)
      status.textContent = `${r.rows.length}${r.truncated ? '+' : ''} rows in ${r.ms.toFixed(0)} ms`
      out.innerHTML =
        `<thead><tr>${r.columns.map((c) => `<th>${esc(c)}</th>`).join('')}</tr></thead>` +
        `<tbody>${r.rows.map((row) => `<tr>${row.map((v) => `<td>${esc(fmtCell(v))}</td>`).join('')}</tr>`).join('')}</tbody>`
    } catch (e) {
      status.textContent = `Error: ${(e as Error).message}`
      out.innerHTML = ''
    } finally {
      $('runSql').removeAttribute('disabled')
    }
  }
  $('runSql').addEventListener('click', () => void run())
  input.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') void run()
  })
}

function fmtCell(v: unknown): string {
  if (v == null) return 'null'
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : Math.abs(v) < 10 ? v.toFixed(4) : v.toFixed(2)
  return String(v)
}

main().catch((e) => {
  document.querySelector('main')!.insertAdjacentHTML('afterbegin', `<p class="error">Could not load the data: ${esc(String(e))}</p>`)
})
