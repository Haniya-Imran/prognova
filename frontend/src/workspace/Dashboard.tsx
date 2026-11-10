/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useState } from 'react'
import { useWorkspace } from '../state/Workspace'
import { api, download, reportUrl, type Filters } from '../lib/api'
import { useLoad } from '../lib/useLoad'
import { Card, Empty, ErrorState, Kpi, Loading, Note, PageHead, Segmented } from '../components/ui'
import { FilterBar } from '../components/Filters'
import { alpha, Chart, palette } from '../components/Chart'
import { money, num, pct } from '../lib/format'
import { NeedsData } from './Quality'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function useDebounced<T>(v: T, ms = 350) {
  const [d, setD] = useState(v)
  useEffect(() => { const t = setTimeout(() => setD(v), ms); return () => clearTimeout(t) }, [v, ms])
  return d
}

function Bars({ rows, cur, onPick, label }: { rows: any[]; cur: string; onPick: (name: string) => void; label: string }) {
  const P = palette()
  return (
    <Chart ariaLabel={label} height={Math.max(240, rows.length * 28 + 50)} onClick={(ev) => { const p = ev?.points?.[0]; if (p) onPick(String(p.y)) }}
      data={[{ type: 'bar', orientation: 'h', y: rows.map((r) => r.name).reverse(), x: rows.map((r) => r.revenue).reverse(),
        customdata: rows.map((r) => [r.share_pct, r.units ?? null, r.orders ?? null]).reverse(), marker: { color: P[0] },
        hovertemplate: `<b>%{y}</b><br>${cur}%{x:,.0f} · %{customdata[0]:.1f}% of revenue<br>%{customdata[1]:,} units · %{customdata[2]:,} orders<br><i>Click to filter</i><extra></extra>` }]}
      layout={{ margin: { l: 200, r: 16, t: 6, b: 36 }, xaxis: { tickprefix: cur }, yaxis: { automargin: true, tickfont: { size: 11 } } }} />
  )
}

export default function Dashboard() {
  const { dataset, filters, setFilters, resetFilters, cur } = useWorkspace()
  const [grain, setGrain] = useState<'auto' | 'day' | 'week' | 'month'>('auto')
  const [metric, setMetric] = useState<'revenue' | 'orders' | 'units'>('revenue')
  const [dlErr, setDlErr] = useState<string | null>(null)
  const ready = dataset?.status === 'ready'
  const f = useDebounced(filters)
  const key = JSON.stringify(f)
  const { data: d, error, loading, retry } = useLoad(ready ? () => api.dashboard(dataset!.id, f, grain === 'auto' ? null : grain) : null, [dataset?.id, ready, key, grain])
  const P = palette()

  if (!ready) return <><PageHead step="Step D" title="Sales Dashboard" /><NeedsData /></>

  const k = d?.kpis
  const c = k?.current
  const g = k?.growth
  const growthLabel = (key: string) => {
    const v = g?.[key]?.vs_previous_period_pct
    return v == null ? 'no earlier period' : `${pct(v)} vs previous ${k.period.days} days`
  }
  const add = (dim: keyof Filters, v: string) => {
    const cur_ = filters[dim] as string[]
    if (!cur_.includes(v)) setFilters({ ...filters, [dim]: [...cur_, v] })
  }
  const metricOk = (m: string) => d?.trend?.[m] !== undefined

  async function dl(kind: string, ext: 'csv' | 'html') {
    setDlErr(null)
    try { await download(reportUrl(dataset!.id, kind, ext, { filters }), `${kind}-${dataset!.id}.${ext}`) } catch (e: any) { setDlErr(e.message) }
  }

  return (
    <>
      <PageHead step="Step D" title="Sales Dashboard"
        lead="Every number here is recalculated from the cleaned transactions for your filters. Click a bar to drill down."
        actions={<>
          <button className="btn" onClick={() => dl('dashboard', 'csv')} disabled={!d}>Export trend CSV</button>
          <button className="btn btn-primary" onClick={() => dl('dashboard', 'html')} disabled={!d}>Download report</button>
        </>} />
      {dlErr && <ErrorState message={dlErr} />}
      <Card><FilterBar filters={filters} onChange={setFilters} onReset={resetFilters} /></Card>

      {loading && !d && <div style={{ marginTop: 16 }}><Loading label="Calculating KPIs and charts…" rows={3} /></div>}
      {error && <div style={{ marginTop: 16 }}><ErrorState message={error} onRetry={retry} /></div>}
      {d && (
        <div className="stack" style={{ marginTop: 16, opacity: loading ? .6 : 1, transition: 'opacity .2s' }} aria-busy={loading}>
          {d.empty ? <Empty title="No sales match these filters">Try a wider date range or remove a filter.</Empty> : <>
            <p className="small muted">Showing {k.period.start} → {k.period.end} ({num(k.period.days)} days).
              {k.previous_period.available ? ` Compared with ${k.previous_period.start} → ${k.previous_period.end}.` : ' No earlier period of the same length exists in the data.'}</p>
            <div className="kpis">
              <Kpi tone="brand" label="Gross revenue" value={money(c.gross_revenue, cur)} delta={g.gross_revenue.vs_previous_period_pct} deltaLabel={growthLabel('gross_revenue')} />
              <Kpi label="Net revenue" value={money(c.net_revenue, cur)} delta={g.net_revenue.vs_previous_period_pct} deltaLabel={growthLabel('net_revenue')}
                info="Gross revenue minus returns and cancellations in the same period. Not profit." />
              {c.orders != null && <Kpi label="Orders" value={num(c.orders)} delta={g.orders.vs_previous_period_pct} deltaLabel={growthLabel('orders')} />}
              {c.units != null && <Kpi label="Units sold" value={num(c.units)} delta={g.units.vs_previous_period_pct} deltaLabel={growthLabel('units')} />}
              {c.avg_order_value != null && <Kpi label="Average order value" value={money(c.avg_order_value, cur, 2)} delta={g.avg_order_value.vs_previous_period_pct} deltaLabel={growthLabel('avg_order_value')} info="Gross revenue ÷ number of orders." />}
              <Kpi label="Revenue growth vs last year" value={pct(g.gross_revenue.vs_last_year_pct)} delta={g.gross_revenue.vs_last_year_pct}
                deltaLabel={k.last_year_period.available ? `vs ${k.last_year_period.start} → ${k.last_year_period.end}` : 'not enough history'} info="Same dates one year earlier, same filters." />
              {k.best_product_by_revenue && <Kpi label="Best-selling product" value={<span className="small-val">{k.best_product_by_revenue.name}</span>} deltaLabel={`${money(k.best_product_by_revenue.value, cur)} · ${k.best_product_by_revenue.share_pct.toFixed(1)}% of revenue`} />}
              {k.top_category && <Kpi label="Top category" value={<span className="small-val">{k.top_category.name}</span>} deltaLabel={`${k.top_category.share_pct.toFixed(1)}% of revenue`} />}
              {k.top_region && <Kpi label="Top region" value={<span className="small-val">{k.top_region.name}</span>} deltaLabel={`${k.top_region.share_pct.toFixed(1)}% of revenue`} />}
              {k.top_store && <Kpi label="Top store" value={<span className="small-val">{k.top_store.name}</span>} deltaLabel={`${k.top_store.share_pct.toFixed(1)}% of revenue`} />}
            </div>

            <Card title="Trend" sub={`Grouped by ${d.grain}. Drag on the chart to zoom; double-click to reset.`}
              actions={<>
                <Segmented label="Metric" value={metric} onChange={setMetric} options={[{ value: 'revenue', label: 'Revenue' }, { value: 'orders', label: 'Orders', disabled: !metricOk('orders') }, { value: 'units', label: 'Units', disabled: !metricOk('units') }]} />
                <Segmented label="Grain" value={grain} onChange={setGrain} options={[{ value: 'auto', label: 'Auto' }, { value: 'day', label: 'Day' }, { value: 'week', label: 'Week' }, { value: 'month', label: 'Month' }]} />
              </>}>
              <Chart ariaLabel={`${metric} trend`} height={340} data={[{ type: d.grain === 'month' ? 'bar' : 'scatter', mode: 'lines', x: d.trend.period, y: d.trend[metric] ?? [],
                line: { color: P[0], width: 2 }, marker: { color: P[0] }, fill: d.grain === 'month' ? undefined : 'tozeroy', fillcolor: alpha(P[0], .14),
                hovertemplate: `%{x|%d %b %Y}<br>${metric === 'revenue' ? cur : ''}%{y:,.0f}<extra></extra>` }]}
                layout={{ yaxis: { tickprefix: metric === 'revenue' ? cur : '' } }} />
            </Card>

            <div className="grid g2">
              {d.top_products && <Card title="Top products" sub="By revenue. Click a bar to filter to that product.">
                <Bars rows={d.top_products} cur={cur} onPick={(n) => add('product', n)} label="Top products by revenue" /></Card>}
              {d.regions && <Card title="Regions" sub="By revenue. Click a bar to drill into that region.">
                <Bars rows={d.regions} cur={cur} onPick={(n) => add('region', n)} label="Revenue by region" /></Card>}
              {d.categories && <Card title="Categories" sub="Click to filter."><Bars rows={d.categories} cur={cur} onPick={(n) => add('category', n)} label="Revenue by category" /></Card>}
              {d.stores && <Card title="Stores" sub="Click to filter."><Bars rows={d.stores} cur={cur} onPick={(n) => add('store', n)} label="Revenue by store" /></Card>}
            </div>

            <div className="grid g2">
              {d.year_overlay?.length > 0 && <Card title="Year vs year" sub="Each line is one year, month by month, to compare like with like.">
                <Chart ariaLabel="Revenue by month for each year" height={300} data={d.year_overlay.map((y: any, i: number) => ({ type: 'scatter', mode: 'lines+markers', name: String(y.year), x: MONTHS, y: y.values, line: { color: P[i % 6], width: 2 }, connectgaps: false, hovertemplate: `${y.year} %{x}: ${cur}%{y:,.0f}<extra></extra>` }))}
                  layout={{ yaxis: { tickprefix: cur } }} /></Card>}
              {d.heatmap && <Card title={d.heatmap.kind === 'weekday_hour' ? 'When sales happen' : 'Weekday × month'} sub="Darker = more revenue.">
                <Chart ariaLabel="Revenue heatmap" height={300} data={[{ type: 'heatmap', x: d.heatmap.x, y: d.heatmap.y, z: d.heatmap.z, colorscale: [[0, '#f1f6fd'], [0.5, alpha(P[0], .55)], [1, '#156bb0']], hovertemplate: `%{y} %{x}<br>${cur}%{z:,.0f}<extra></extra>`, showscale: false }]}
                  layout={{ yaxis: { autorange: 'reversed' }, xaxis: { title: { text: d.heatmap.x_title } } }} /></Card>}
              {d.pareto && <Card title="Revenue concentration" info="A Pareto curve: how much revenue comes from the best-selling share of products."
                sub={`Top 20% of products bring ${d.pareto.top20_share_pct}% of revenue; ${num(d.pareto.products_for_80pct)} of ${num(d.pareto.products)} products make 80%.`}>
                <Chart ariaLabel="Pareto curve of product revenue" height={280} data={[{ type: 'scatter', mode: 'lines', x: d.pareto.curve.map((p: any) => p.pct_products), y: d.pareto.curve.map((p: any) => p.pct_revenue), line: { color: P[0], width: 2.5 }, fill: 'tozeroy', fillcolor: alpha(P[0], .12), hovertemplate: 'Top %{x:.0f}% of products → %{y:.0f}% of revenue<extra></extra>' }]}
                  layout={{ xaxis: { ticksuffix: '%', title: { text: 'Share of products (best first)' } }, yaxis: { ticksuffix: '%', range: [0, 101] } }} /></Card>}
              {d.returns_by_month?.length > 0 && <Card title="Returns" sub={`Returns in this view: ${money(c.returns_value, cur)} (${pct(c.return_rate_pct, 1, false)} of gross).`}>
                <Chart ariaLabel="Returns by month" height={280} data={[{ type: 'bar', x: d.returns_by_month.map((r: any) => r.month), y: d.returns_by_month.map((r: any) => r.returns), marker: { color: P[3] }, customdata: d.returns_by_month.map((r: any) => r.rate_pct), hovertemplate: `%{x}<br>${cur}%{y:,.0f} · %{customdata:.1f}% of sales<extra></extra>` }]}
                  layout={{ yaxis: { tickprefix: cur } }} /></Card>}
            </div>
            <Note>Charts can be saved as PNG with the camera icon that appears when you hover over a chart.</Note>
          </>}
        </div>
      )}
    </>
  )
}
