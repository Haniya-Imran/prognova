import { Link } from 'react-router-dom'
import { useWorkspace } from '../state/Workspace'
import { api } from '../lib/api'
import { useLoad } from '../lib/useLoad'
import { Card, ErrorState, Kpi, Loading, Note, PageHead } from '../components/ui'
import { money, num, pct } from '../lib/format'
import { Chart, palette } from '../components/Chart'

const PIPE = [
  { k: 'A', to: '/app/data', t: 'Data Hub', d: 'Open the real demo data or upload your own CSV.' },
  { k: 'B', to: '/app/quality', t: 'Data Quality', d: 'Missing values, duplicates, returns, outliers — and every cleaning decision.' },
  { k: 'C', to: '/app/eda', t: 'EDA Studio', d: 'Trends, seasonality, distributions, top and bottom performers.' },
  { k: 'D', to: '/app/dashboard', t: 'Sales Dashboard', d: 'Filter by date, product and region; KPIs update live.' },
  { k: 'E', to: '/app/forecast', t: 'Forecasting Lab', d: 'Models compared on past data, then the next 3 months.' },
  { k: 'F', to: '/app/insights', t: 'Business Insights', d: 'Plain-language findings with the numbers behind them.' },
  { k: 'G', to: '/app/reports', t: 'Reports', d: 'Download CSVs and HTML reports of what you see.' },
]

export default function Overview() {
  const { dataset, cur } = useWorkspace()
  const ready = dataset?.status === 'ready'
  const eda = useLoad(ready ? () => api.eda(dataset!.id) : null, [dataset?.id, ready])
  const t = eda.data?.overview?.totals
  const P = palette()
  const months = eda.data?.time?.monthly as { month: string; revenue: number; complete: boolean }[] | undefined

  return (
    <>
      <PageHead step="Prognova workspace" title="Overview"
        lead={<>A guided path from raw transactions to a tested 3-month forecast. Each step uses the same cleaned data, so numbers agree everywhere.</>} />

      {!ready && dataset && (
        <Note tone="warn">Your upload is waiting for its column mapping. <Link to="/app/data">Finish step A</Link> to unlock the rest.</Note>
      )}

      {ready && (
        <div className="stack">
          <Card title={dataset!.name} sub={dataset!.meta?.description}
            actions={dataset!.source === 'sample' ? <a className="btn btn-sm" href={dataset!.meta.source_url} target="_blank" rel="noreferrer">Source ↗</a> : undefined}>
            {eda.loading && <Loading label="Summarising the dataset…" rows={1} />}
            {eda.error && <ErrorState message={eda.error} onRetry={eda.retry} />}
            {t && (
              <div className="kpis">
                <Kpi tone="brand" label="Gross revenue" value={money(t.gross_revenue, cur)} deltaLabel={`${dataset!.date_min} → ${dataset!.date_max}`} />
                <Kpi label="Net revenue" value={money(t.net_revenue, cur)} deltaLabel={`after ${pct(t.return_rate_pct, 1, false)} returns`}
                  info="Gross sales minus returns and cancellations. This is revenue, not profit — there is no cost data." />
                <Kpi label="Orders" value={num(t.orders)} deltaLabel={t.avg_order_value ? `avg ${money(t.avg_order_value, cur)} per order` : ''} />
                <Kpi label="Units sold" value={num(t.units)} deltaLabel={t.customers ? `${num(t.customers)} identified customers` : ''} />
              </div>
            )}
          </Card>
          {months && (
            <Card title="Monthly revenue at a glance" sub="Each bar is one calendar month of gross sales. A lighter bar means the month is only partly covered by the data.">
              <Chart ariaLabel="Monthly gross revenue" height={260}
                data={[{ type: 'bar', x: months.map((m) => m.month), y: months.map((m) => m.revenue),
                  marker: { color: months.map((m) => m.complete ? P[0] : P[3]), opacity: months.map((m) => m.complete ? 1 : .45) },
                  hovertemplate: `%{x|%b %Y}<br>${cur}%{y:,.0f}<extra></extra>` }]}
                layout={{ xaxis: { type: 'date', tickformat: '%b %y' }, yaxis: { tickprefix: cur } }} />
            </Card>
          )}
        </div>
      )}

      <h2 style={{ fontSize: 24, margin: '30px 0 12px' }}>The workflow</h2>
      <div className="pipeline">
        {PIPE.map((p) => (
          <Link key={p.k} to={p.to} className="pipe"><span className="k">STEP {p.k}</span><b>{p.t}</b><span>{p.d}</span></Link>
        ))}
      </div>
    </>
  )
}
