/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState } from 'react'
import { useWorkspace } from '../state/Workspace'
import { api } from '../lib/api'
import { useLoad } from '../lib/useLoad'
import { Card, Empty, ErrorState, Kpi, Loading, PageHead, Segmented } from '../components/ui'
import { alpha, Chart, palette } from '../components/Chart'
import { money, num, pct } from '../lib/format'
import { NeedsData } from './Quality'

type Tab = 'summary' | 'time' | 'season' | 'dims' | 'dist' | 'corr' | 'returns'

function StatsTable({ stats, cur }: { stats: Record<string, any>; cur: string }) {
  const cols = Object.keys(stats).filter((k) => stats[k] && Object.keys(stats[k]).length)
  const rows = ['count', 'mean', 'std', 'min', 'p25', 'median', 'p75', 'p95', 'max', 'skew']
  const money_ = (c: string) => ['revenue', 'unit_price', 'order_value'].includes(c)
  return (
    <div className="table-wrap"><table className="tbl">
      <thead><tr><th>Statistic</th>{cols.map((c) => <th className="n" key={c}>{c.replace('_', ' ')}</th>)}</tr></thead>
      <tbody>{rows.map((r) => <tr key={r}><td>{r}</td>{cols.map((c) => <td className="n" key={c}>{r === 'count' ? num(stats[c][r]) : r === 'skew' ? num(stats[c][r], 2) : money_(c) ? money(stats[c][r], cur, 2) : num(stats[c][r], 2)}</td>)}</tr>)}</tbody>
    </table></div>
  )
}

function Hist({ h, title, cur }: { h: any; title: string; cur: string }) {
  if (!h?.edges?.length) return null
  const P = palette()
  const mids = h.edges.slice(0, -1).map((e: number, i: number) => Math.sqrt(e * h.edges[i + 1]))
  return (
    <Chart ariaLabel={title} height={280}
      data={[{ type: 'bar', x: mids, y: h.counts, marker: { color: P[0] }, width: h.edges.slice(0, -1).map((e: number, i: number) => (h.edges[i + 1] - e) * 0.95),
        hovertemplate: `≈ ${cur}%{x:,.2f}<br>%{y:,} rows<extra></extra>` }]}
      layout={{ xaxis: { type: 'log', title: { text: `${title} (log scale)` }, tickprefix: cur }, yaxis: { title: { text: 'Count' } }, bargap: 0 }} />
  )
}

function DimTable({ rows, cur, basis }: { rows: any[]; cur: string; basis?: string }) {
  return (
    <div className="table-wrap" style={{ maxHeight: 460 }}><table className="tbl">
      <thead><tr><th>#</th><th>Name</th><th className="n">Revenue</th><th className="n">Share</th><th className="n">Units</th><th className="n">Orders</th><th className="n" title={basis}>YoY growth</th></tr></thead>
      <tbody>{rows.map((r, i) => <tr key={r.name}><td className="muted">{i + 1}</td><td className="clip" title={r.name}>{r.name}</td><td className="n">{money(r.revenue, cur)}</td>
        <td className="n">{r.share_pct < 0.01 ? '<0.01%' : `${r.share_pct.toFixed(2)}%`}</td><td className="n">{num(r.units)}</td><td className="n">{num(r.orders)}</td>
        <td className="n" style={{ color: r.growth_pct == null ? undefined : r.growth_pct >= 0 ? 'var(--good)' : 'var(--bad)' }}>{pct(r.growth_pct, 1)}</td></tr>)}</tbody>
    </table></div>
  )
}

export default function Eda() {
  const { dataset, cur } = useWorkspace()
  const ready = dataset?.status === 'ready'
  const { data: e, error, loading, retry } = useLoad(ready ? () => api.eda(dataset!.id) : null, [dataset?.id, ready])
  const [tab, setTab] = useState<Tab>('summary')
  const [grain, setGrain] = useState<'daily' | 'weekly' | 'monthly'>('weekly')
  const [dim, setDim] = useState<string>('product')
  const P = palette()

  if (!ready) return <><PageHead step="Step C" title="EDA Studio" /><NeedsData /></>
  const head = <PageHead step="Step C" title="EDA Studio" lead="Exploratory analysis of the whole cleaned dataset: what is normal, what changes over time, and what drives revenue." />
  if (loading && !e) return <>{head}<Loading label="Exploring every row… (first time takes a few seconds)" rows={4} /></>
  if (error) return <>{head}<ErrorState message={error} onRetry={retry} /></>
  if (!e) return head

  const o = e.overview, t = e.time
  const dims = Object.entries(e.dimensions).filter(([, v]) => v).map(([k]) => k)
  const d = e.dimensions[dim] || e.dimensions[dims[0]]
  const months = t.monthly.filter((m: any) => m.complete)

  return (
    <>
      {head}
      <div className="row" style={{ marginBottom: 16 }}>
        <Segmented label="EDA section" value={tab} onChange={setTab} options={[
          { value: 'summary', label: 'Summary' }, { value: 'time', label: 'Trends' }, { value: 'season', label: 'Seasonality' },
          { value: 'dims', label: 'Products & regions' }, { value: 'dist', label: 'Distributions' }, { value: 'corr', label: 'Correlation' },
          { value: 'returns', label: 'Returns', disabled: !e.returns },
        ]} />
      </div>

      {tab === 'summary' && (
        <div className="stack">
          <div className="kpis">
            <Kpi label="Records (raw)" value={num(o.raw_rows)} deltaLabel={`${o.raw_columns} columns`} />
            <Kpi label="Clean sales lines" value={num(o.clean_rows)} deltaLabel={`${num(o.return_rows)} return lines`} />
            <Kpi label="Date range" value={<span className="small-val">{o.date_min} → {o.date_max}</span>} />
            <Kpi label="Missing cells (raw)" value={num(o.missing_cells)} deltaLabel={`${num(o.duplicate_rows)} duplicate rows`} />
            <Kpi label="Avg sales per day" value={money(o.totals.avg_daily_revenue, cur)} deltaLabel={`${num(o.totals.selling_days)} selling days`} />
          </div>
          <div className="grid g2">
            <Card title="Line-level statistics" sub="Each row of the cleaned table is one product line on an order." info="p25/p75 are the 25th/75th percentiles: a quarter of lines are below p25. Skew > 1 means a long tail of very large values.">
              <StatsTable stats={o.line_stats} cur={cur} />
            </Card>
            {o.order_stats && <Card title="Order-level statistics" sub="Lines grouped into orders (invoices).">
              <StatsTable stats={{ order_value: o.order_stats.order_value, lines_per_order: o.order_stats.lines_per_order }} cur={cur} />
            </Card>}
            <Card title="Columns">
              <p className="small"><b>Numeric:</b> {o.numeric_columns.join(', ')}</p>
              <p className="small" style={{ marginTop: 6 }}><b>Categorical (distinct values):</b> {Object.entries(o.cardinality).map(([k, v]) => `${k} (${num(v as number)})`).join(', ')}</p>
              <p className="small" style={{ marginTop: 6 }}><b>Original columns:</b> {o.column_names.join(', ')}</p>
            </Card>
            <Card title="Yearly totals" sub="Partial years are marked; compare full years only.">
              <div className="table-wrap"><table className="tbl"><thead><tr><th>Year</th><th className="n">Revenue</th><th className="n">Months</th><th>Coverage</th></tr></thead>
                <tbody>{t.yearly.map((y: any) => <tr key={y.year}><td>{y.year}</td><td className="n">{money(y.revenue, cur)}</td><td className="n">{y.months}</td><td>{y.full_year ? 'Full year' : 'Partial'}</td></tr>)}</tbody></table></div>
            </Card>
          </div>
        </div>
      )}

      {tab === 'time' && (
        <div className="stack">
          <Card title="Sales over time" sub="Daily view also shows a 28-day moving average to see the underlying trend."
            actions={<Segmented label="Time grain" value={grain} onChange={setGrain} options={[{ value: 'daily', label: 'Daily' }, { value: 'weekly', label: 'Weekly' }, { value: 'monthly', label: 'Monthly' }]} />}>
            {grain === 'daily' && <Chart ariaLabel="Daily revenue with 28-day average" height={360} data={[
              { type: 'scatter', mode: 'lines', x: t.daily.date, y: t.daily.revenue, name: 'Daily revenue', line: { color: P[0], width: 1 }, opacity: .45 },
              { type: 'scatter', mode: 'lines', x: t.daily.date, y: t.daily.rolling_28d_mean, name: '28-day average', line: { color: P[1], width: 2.5 } }]}
              layout={{ yaxis: { tickprefix: cur }, xaxis: { rangeslider: { visible: true, thickness: .06 } } }} />}
            {grain === 'weekly' && <Chart ariaLabel="Weekly revenue" height={360} data={[{ type: 'scatter', mode: 'lines', fill: 'tozeroy', x: t.weekly.week, y: t.weekly.revenue, line: { color: P[0] }, fillcolor: alpha(P[0], .14), name: 'Weekly revenue', hovertemplate: `Week of %{x|%d %b %Y}<br>${cur}%{y:,.0f}<extra></extra>` }]} layout={{ yaxis: { tickprefix: cur } }} />}
            {grain === 'monthly' && <Chart ariaLabel="Monthly revenue" height={360} data={[{ type: 'bar', x: t.monthly.map((m: any) => m.month), y: t.monthly.map((m: any) => m.revenue), marker: { color: t.monthly.map((m: any) => m.complete ? P[0] : P[3]) }, hovertemplate: `%{x|%b %Y}<br>${cur}%{y:,.0f}<extra></extra>` }]} layout={{ yaxis: { tickprefix: cur }, xaxis: { type: 'date', tickformat: '%b %y' } }} />}
          </Card>
          <div className="grid g2">
            <Card title="Month-over-month growth" sub="Change vs the previous month. Big swings around November reflect seasonality, not trend.">
              <Chart ariaLabel="Month over month growth" height={300} data={[{ type: 'bar', x: months.map((m: any) => m.month), y: months.map((m: any) => m.mom_pct), marker: { color: months.map((m: any) => (m.mom_pct ?? 0) >= 0 ? P[2] : P[3]) }, hovertemplate: '%{x|%b %Y}: %{y:.1f}%<extra></extra>' }]} layout={{ yaxis: { ticksuffix: '%' }, xaxis: { type: 'date', tickformat: '%b %y' } }} />
            </Card>
            <Card title="Year-over-year growth" sub="Same month, one year apart — the fair comparison for seasonal sales.">
              {months.some((m: any) => m.yoy_pct != null) ? (
                <Chart ariaLabel="Year over year growth" height={300} data={[{ type: 'bar', x: months.filter((m: any) => m.yoy_pct != null).map((m: any) => m.month), y: months.filter((m: any) => m.yoy_pct != null).map((m: any) => m.yoy_pct), marker: { color: P[1] }, hovertemplate: '%{x|%b %Y}: %{y:.1f}% vs a year earlier<extra></extra>' }]} layout={{ yaxis: { ticksuffix: '%' }, xaxis: { type: 'date', tickformat: '%b %y' } }} />
              ) : <Empty title="Not enough history">Year-over-year needs at least 13 complete months.</Empty>}
            </Card>
          </div>
          <div className="grid g3">
            <Card title="Peak months">{t.peak_months.map((m: any) => <p key={m.month} className="row" style={{ justifyContent: 'space-between' }}><span>{m.month}</span><b className="num">{money(m.revenue, cur)}</b></p>)}</Card>
            <Card title="Low months">{t.low_months.map((m: any) => <p key={m.month} className="row" style={{ justifyContent: 'space-between' }}><span>{m.month}</span><b className="num">{money(m.revenue, cur)}</b></p>)}</Card>
            <Card title="Volatility" info={t.volatility.note}>
              <p className="small">Daily variation: <b>{num(t.volatility.daily_cv_pct, 1)}%</b></p>
              <p className="small">Monthly variation: <b>{num(t.volatility.monthly_cv_pct, 1)}%</b></p>
              <p className="small">Days with no sales: <b>{num(t.volatility.zero_sales_days)}</b> of {num(t.volatility.total_days)}</p>
            </Card>
          </div>
        </div>
      )}

      {tab === 'season' && (
        <div className="grid g2">
          <Card className="span2" title="Seasonality index by month" sub={t.seasonality_index.note}>
            <Chart ariaLabel="Seasonality index" height={300} data={[{ type: 'bar', x: t.seasonality_index.month, y: t.seasonality_index.index, marker: { color: t.seasonality_index.index.map((v: number) => v >= 100 ? P[0] : P[3]) }, hovertemplate: '%{x}: %{y:.0f}<extra></extra>' },
              { type: 'scatter', mode: 'lines', x: t.seasonality_index.month, y: t.seasonality_index.month.map(() => 100), line: { color: P[1], dash: 'dot' }, name: 'Average month', hoverinfo: 'skip' }]}
              layout={{ showlegend: false }} />
          </Card>
          <Card title="Average sales by weekday" sub="Per selling day. A missing bar means (almost) no trading on that day.">
            <Chart ariaLabel="Average revenue by weekday" height={280} data={[{ type: 'bar', x: t.weekday.day, y: t.weekday.avg_revenue_per_selling_day.map((v: number, i: number) => t.weekday.selling_days[i] >= 5 ? v : null), marker: { color: P[2] }, customdata: t.weekday.selling_days, hovertemplate: `%{x}: ${cur}%{y:,.0f}<br>%{customdata} selling days<extra></extra>` }]} layout={{ yaxis: { tickprefix: cur } }} />
          </Card>
          {t.hour ? <Card title="Revenue by hour of day" sub="When orders are placed.">
            <Chart ariaLabel="Revenue by hour" height={280} data={[{ type: 'bar', x: t.hour.hours, y: t.hour.revenue, marker: { color: P[4] }, hovertemplate: `%{x}: ${cur}%{y:,.0f}<extra></extra>` }]} layout={{ yaxis: { tickprefix: cur } }} />
          </Card> : <Card title="Revenue by hour"><Empty title="No time of day">This dataset has dates only.</Empty></Card>}
        </div>
      )}

      {tab === 'dims' && (
        <div className="stack">
          <Segmented label="Dimension" value={dims.includes(dim) ? dim : dims[0]} onChange={setDim} options={dims.map((k) => ({ value: k, label: k[0].toUpperCase() + k.slice(1) }))} />
          {!d ? <Empty title="No dimensions">This dataset has no product, category, region or store column.</Empty> : (
            <>
              <Card title={`Top ${d.top.length} by revenue`} sub={`${num(d.count)} in total. The top ${d.top.length} bring ${d.top_share_pct}% of revenue. YoY growth: ${d.growth_basis}.`}>
                <Chart ariaLabel={`Top ${dim} by revenue`} height={Math.max(260, d.top.length * 26 + 60)} data={[{ type: 'bar', orientation: 'h', y: d.top.map((r: any) => r.name).reverse(), x: d.top.map((r: any) => r.revenue).reverse(), marker: { color: P[0] }, hovertemplate: `%{y}<br>${cur}%{x:,.0f}<extra></extra>` }]}
                  layout={{ margin: { l: 220, r: 16, t: 8, b: 40 }, xaxis: { tickprefix: cur }, yaxis: { automargin: true, tickfont: { size: 11 } } }} />
                <DimTable rows={d.top} cur={cur} basis={d.growth_basis} />
              </Card>
              <Card title="Lowest performers" sub="Among items sold in at least as many months as the typical item, so one-off listings don't crowd the list.">
                <DimTable rows={d.bottom} cur={cur} basis={d.growth_basis} />
              </Card>
            </>
          )}
        </div>
      )}

      {tab === 'dist' && (
        <div className="grid g2">
          {e.distributions.order_value && <Card title="Order value distribution" sub={e.distributions.order_value_note}><Hist h={e.distributions.order_value} title="Order value" cur={cur} /></Card>}
          <Card title="Line value distribution" sub="Value of each product line."><Hist h={e.distributions.line_revenue} title="Line value" cur={cur} /></Card>
          {e.distributions.unit_price && <Card title="Unit price distribution"><Hist h={e.distributions.unit_price} title="Unit price" cur={cur} /></Card>}
          {e.distributions.quantity && <Card title="Quantity per line"><Hist h={e.distributions.quantity} title="Quantity" cur="" /></Card>}
        </div>
      )}

      {tab === 'corr' && (e.correlation ? (
        <Card title="How order measures move together" sub={e.correlation.note}>
          <Chart ariaLabel="Correlation heatmap" height={420} data={[{ type: 'heatmap', x: e.correlation.labels, y: e.correlation.labels, z: e.correlation.spearman, zmin: -1, zmax: 1,
            colorscale: [[0, P[3]], [0.5, '#f4f7fc'], [1, P[0]]], text: e.correlation.spearman.map((r: number[]) => r.map((v) => v.toFixed(2))), texttemplate: '%{text}', hovertemplate: '%{y} vs %{x}: %{z:.2f}<extra></extra>' }]}
            layout={{ margin: { l: 110, r: 20, t: 10, b: 80 } }} />
        </Card>) : <Empty title="Not enough numeric columns for correlation" />)}

      {tab === 'returns' && e.returns && (
        <div className="grid g2">
          <Card title="Return rate by month" sub={`${num(e.returns.lines)} return lines worth ${money(e.returns.total_returns, cur)} in total.`}>
            <Chart ariaLabel="Return rate by month" height={300} data={[{ type: 'scatter', mode: 'lines+markers', x: e.returns.by_month.map((r: any) => r.month), y: e.returns.by_month.map((r: any) => r.rate_pct), line: { color: P[3] }, hovertemplate: '%{x}: %{y:.1f}% of sales<extra></extra>' }]} layout={{ yaxis: { ticksuffix: '%' } }} />
          </Card>
          {e.returns.top_returned_products && <Card title="Most returned products (by value)" sub="Includes order-entry corrections, e.g. a huge order cancelled the same day.">
            <div className="table-wrap"><table className="tbl"><thead><tr><th>Product</th><th className="n">Returned value</th></tr></thead>
              <tbody>{e.returns.top_returned_products.map((r: any) => <tr key={r.name}><td className="clip" title={r.name}>{r.name}</td><td className="n">{money(r.returns, cur)}</td></tr>)}</tbody></table></div>
          </Card>}
        </div>
      )}
    </>
  )
}
