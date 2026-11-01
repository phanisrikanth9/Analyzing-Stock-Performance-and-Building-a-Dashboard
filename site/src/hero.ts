// The hero: "what $100 became", drawn as SVG lines that animate in, and scrubbable.
// Moving the pointer (or arrow keys) across the chart sets a date; the big numbers above
// show every stock's value on that date. Reading the market by moving through it.

import type { Dashboard, Summary } from './types'

const NS = 'http://www.w3.org/2000/svg'
const fmtDate = (iso: string) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })

interface Line {
  s: Summary
  values: number[] // growth of $100 from the range start
}

export class Hero {
  private svg: SVGSVGElement
  private range = 12
  private dates: string[] = []
  private lines: Line[] = []
  private idx = 0
  private x = (i: number) => i
  private y = (v: number) => v
  private reduced = matchMedia('(prefers-reduced-motion: reduce)').matches

  constructor(
    private root: HTMLElement,
    private dash: Dashboard,
  ) {
    this.svg = root.querySelector('svg.hero-chart') as SVGSVGElement
    this.svg.addEventListener('pointermove', (e) => this.onPointer(e))
    this.svg.addEventListener('pointerleave', () => this.setIndex(this.dates.length - 1))
    this.svg.addEventListener('keydown', (e) => this.onKey(e))
    new ResizeObserver(() => this.draw(false)).observe(this.svg)
    root.querySelectorAll<HTMLButtonElement>('[data-range]').forEach((b) =>
      b.addEventListener('click', () => {
        root.querySelectorAll('[data-range]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)))
        this.setRange(Number(b.dataset.range))
      }),
    )
    this.setRange(12)
  }

  setRange(months: number) {
    this.range = months
    // Every series shares trading days; use the first stock's calendar.
    const ref = this.dash.series[this.dash.summary[0].ticker]
    const last = new Date(`${ref.date[ref.date.length - 1]}T00:00:00`)
    const start = new Date(last)
    start.setMonth(start.getMonth() - months)
    const startIso = start.toISOString().slice(0, 10)
    const i0 = Math.max(0, ref.date.findIndex((d) => d >= startIso))
    this.dates = ref.date.slice(i0)
    this.lines = this.dash.summary.map((s) => {
      const se = this.dash.series[s.ticker]
      // Align on dates (a ticker could be missing a day); carry the last value forward.
      const byDate = new Map(se.date.map((d, i) => [d, se.adj_close[i]]))
      let lastVal = byDate.get(this.dates[0]) ?? se.adj_close[0]
      const base = lastVal
      const values = this.dates.map((d) => {
        const v = byDate.get(d)
        if (v != null) lastVal = v
        return (100 * lastVal) / base
      })
      return { s, values }
    })
    this.root.dataset.range = String(months)
    this.draw(true)
    this.setIndex(this.dates.length - 1)
  }

  private draw(animate: boolean) {
    const svg = this.svg
    const w = svg.clientWidth || 1000
    const h = svg.clientHeight || 360
    svg.setAttribute('viewBox', `0 0 ${w} ${h}`)
    const pad = { l: 52, r: 56, t: 16, b: 28 }
    const all = this.lines.flatMap((l) => l.values)
    const log = this.range > 12
    const tf = (v: number) => (log ? Math.log(v) : v)
    const lo = tf(Math.min(...all, 100) * 0.97)
    const hi = tf(Math.max(...all, 100) * 1.03)
    const n = this.dates.length - 1 || 1
    this.x = (i) => pad.l + (i / n) * (w - pad.l - pad.r)
    this.y = (v) => pad.t + (1 - (tf(v) - lo) / (hi - lo)) * (h - pad.t - pad.b)

    svg.replaceChildren()
    // Gridlines at round dollar values, labelled on the right edge.
    const grid = el('g', { class: 'grid' })
    const inv = (t: number) => (log ? Math.exp(t) : t)
    for (const v of ticks(inv(lo), inv(hi), log, Math.min(...all), Math.max(...all))) {
      const yy = this.y(v)
      if (yy < pad.t || yy > h - pad.b) continue
      grid.append(el('line', { x1: pad.l, x2: w - pad.r, y1: yy, y2: yy, class: v === 100 ? 'base' : '' }))
      const t = el('text', { x: 0, y: yy + 4, class: 'y' })
      t.textContent = `$${v >= 1000 ? Math.round(v).toLocaleString() : Math.round(v)}`
      grid.append(t)
    }
    // Month labels along the bottom.
    let lastMonth = ''
    const every = this.range <= 6 ? 1 : this.range <= 12 ? 2 : this.range <= 36 ? 6 : 12
    this.dates.forEach((d, i) => {
      const m = d.slice(0, 7)
      if (m === lastMonth) return
      lastMonth = m
      const month = Number(d.slice(5, 7)) - 1
      if (month % every !== 0) return
      const t = el('text', { x: this.x(i), y: h - 6, class: 'month' })
      t.textContent = new Date(`${d}T12:00:00`).toLocaleDateString('en-US', every >= 12 ? { year: 'numeric' } : { month: 'short' })
      grid.append(t)
    })
    svg.append(grid)

    // Benchmark first so stocks sit on top of it.
    const ordered = [...this.lines].sort((a, b) => Number(b.s.is_benchmark) - Number(a.s.is_benchmark))
    ordered.forEach((l, k) => {
      const d = l.values.map((v, i) => `${i ? 'L' : 'M'}${this.x(i).toFixed(1)},${this.y(v).toFixed(1)}`).join('')
      const path = el('path', { d, class: `line ${l.s.is_benchmark ? 'bench' : ''}`, stroke: l.s.color, 'data-t': l.s.ticker })
      svg.append(path)
      if (animate && !this.reduced) {
        const len = (path as SVGPathElement).getTotalLength()
        path.style.strokeDasharray = `${len}`
        path.style.strokeDashoffset = `${len}`
        path.animate([{ strokeDashoffset: len }, { strokeDashoffset: 0 }], {
          duration: 1400,
          delay: 120 * k,
          easing: 'cubic-bezier(.3,.7,.2,1)',
          fill: 'forwards',
        })
      }
      // End-of-line label
      const last = l.values[l.values.length - 1]
      const lab = el('text', { x: this.x(n) + 8, y: this.y(last) + 4, class: 'end', fill: l.s.color, 'data-t': l.s.ticker })
      lab.textContent = l.s.ticker
      svg.append(lab)
    })
    nudgeLabels(svg)

    // Scrubber
    const cross = el('g', { class: 'cross' })
    cross.append(el('line', { y1: pad.t, y2: h - pad.b, x1: 0, x2: 0 }))
    for (const l of ordered) cross.append(el('circle', { r: 4.5, fill: l.s.color, 'data-t': l.s.ticker }))
    svg.append(cross)
    this.renderCross()
  }

  private onPointer(e: PointerEvent) {
    const r = this.svg.getBoundingClientRect()
    const px = ((e.clientX - r.left) / r.width) * (this.svg.viewBox.baseVal.width || r.width)
    let best = 0
    let bestD = Infinity
    for (let i = 0; i < this.dates.length; i++) {
      const d = Math.abs(this.x(i) - px)
      if (d < bestD) {
        bestD = d
        best = i
      }
    }
    this.setIndex(best)
  }

  private onKey(e: KeyboardEvent) {
    const step = e.shiftKey ? 20 : 1
    if (e.key === 'ArrowLeft') this.setIndex(Math.max(0, this.idx - step))
    else if (e.key === 'ArrowRight') this.setIndex(Math.min(this.dates.length - 1, this.idx + step))
    else if (e.key === 'Home') this.setIndex(0)
    else if (e.key === 'End') this.setIndex(this.dates.length - 1)
    else return
    e.preventDefault()
  }

  private setIndex(i: number) {
    this.idx = i
    this.renderCross()
    const date = this.dates[i]
    const live = i === this.dates.length - 1
    this.root.querySelector('.scrub-date')!.textContent = fmtDate(date)
    this.root.querySelector('.scrub-hint')!.textContent = live ? 'latest close · move across the chart to travel back' : 'drag or use ← → to move'
    const rows = this.root.querySelector('.readout')!
    const sorted = [...this.lines].sort((a, b) => b.values[i] - a.values[i])
    // Re-order rows by value with a FLIP animation so the ranking visibly reshuffles.
    const before = new Map([...rows.children].map((c) => [(c as HTMLElement).dataset.t!, c.getBoundingClientRect().top]))
    for (const l of sorted) {
      let row = rows.querySelector<HTMLElement>(`[data-t="${l.s.ticker}"]`)
      if (!row) {
        row = document.createElement('div')
        row.className = `row ${l.s.is_benchmark ? 'bench' : ''}`
        row.dataset.t = l.s.ticker
        row.style.setProperty('--c', l.s.color)
        row.innerHTML = `<span class="tk">${l.s.ticker}</span><span class="nm">${l.s.name}</span><span class="val"></span><span class="chg"></span>`
        row.addEventListener('pointerenter', () => this.focusLine(l.s.ticker))
        row.addEventListener('pointerleave', () => this.focusLine(null))
      }
      const v = l.values[i]
      row.querySelector('.val')!.textContent = `$${v.toFixed(0)}`
      const chg = row.querySelector('.chg')!
      chg.textContent = `${v >= 100 ? '+' : '−'}${Math.abs(v - 100).toFixed(1)}%`
      chg.className = `chg ${v >= 100 ? 'up' : 'down'}`
      rows.append(row)
    }
    if (!this.reduced) {
      for (const c of rows.children) {
        const el = c as HTMLElement
        const was = before.get(el.dataset.t!)
        if (was == null) continue
        const dy = was - el.getBoundingClientRect().top
        if (Math.abs(dy) > 1) el.animate([{ transform: `translateY(${dy}px)` }, { transform: 'none' }], { duration: 260, easing: 'ease-out' })
      }
    }
    this.svg.setAttribute('aria-valuetext', `${fmtDate(date)}: ${sorted.map((l) => `${l.s.ticker} $${l.values[i].toFixed(0)}`).join(', ')}`)
  }

  private renderCross() {
    const g = this.svg.querySelector('.cross')
    if (!g) return
    const x = this.x(this.idx)
    const line = g.querySelector('line')!
    line.setAttribute('x1', String(x))
    line.setAttribute('x2', String(x))
    for (const c of g.querySelectorAll('circle')) {
      const l = this.lines.find((l) => l.s.ticker === c.getAttribute('data-t'))!
      c.setAttribute('cx', String(x))
      c.setAttribute('cy', String(this.y(l.values[this.idx])))
    }
    g.classList.toggle('at-end', this.idx === this.dates.length - 1)
  }

  private focusLine(t: string | null) {
    this.svg.classList.toggle('focusing', !!t)
    this.svg.querySelectorAll('[data-t]').forEach((n) => n.classList.toggle('hot', n.getAttribute('data-t') === t))
  }
}

function el(tag: string, attrs: Record<string, string | number>) {
  const n = document.createElementNS(NS, tag)
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, String(v))
  return n as SVGElement
}

/** Round gridline values: 100 always, then a sensible step. */
function ticks(lo: number, hi: number, log: boolean, minV: number, maxV: number): number[] {
  const out = new Set<number>([100])
  if (log) {
    for (const v of [25, 50, 100, 200, 400, 800, 1600, 3200]) if (v >= lo && v <= hi) out.add(v)
  } else {
    const span = hi - lo
    const raw = span / 4
    const mag = 10 ** Math.floor(Math.log10(raw))
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw
    for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) out.add(Math.round(v))
  }
  return [...out].filter((v) => v >= Math.min(lo, minV) && v <= Math.max(hi, maxV))
}

/** Keep end-of-line labels from overlapping when lines finish close together. */
function nudgeLabels(svg: SVGSVGElement) {
  const labels = [...svg.querySelectorAll<SVGTextElement>('text.end')].sort((a, b) => Number(a.getAttribute('y')) - Number(b.getAttribute('y')))
  for (let i = 1; i < labels.length; i++) {
    const prev = Number(labels[i - 1].getAttribute('y'))
    const cur = Number(labels[i].getAttribute('y'))
    if (cur - prev < 14) labels[i].setAttribute('y', String(prev + 14))
  }
}
