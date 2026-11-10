/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState } from 'react'
import { useWorkspace } from '../state/Workspace'
import { download, reportUrl } from '../lib/api'
import { Card, ErrorState, Note, PageHead } from '../components/ui'
import { NeedsData } from './Quality'

const ITEMS = [
  { kind: 'eda', ext: 'html', t: 'EDA report', d: 'Dataset overview, monthly table, seasonality, top products/regions, forecast summary and insights.', f: false },
  { kind: 'dashboard', ext: 'html', t: 'Dashboard report', d: 'KPIs, trend and top lists for the filters currently set on the dashboard.', f: true },
  { kind: 'forecast', ext: 'html', t: 'Forecast report', d: 'Next 3 months with ranges, model comparison, limitations and insights.', f: false },
  { kind: 'forecast', ext: 'csv', t: 'Forecast CSV', d: 'Month, forecast, 80% and 95% bounds, same month last year.', f: false },
  { kind: 'backtest', ext: 'csv', t: 'Backtest CSV', d: 'Every backtest origin, month, horizon, actual and predicted value.', f: false },
  { kind: 'models', ext: 'csv', t: 'Model comparison CSV', d: 'All candidate models with WAPE, MAE, RMSE, sMAPE, MAPE and status.', f: false },
  { kind: 'monthly', ext: 'csv', t: 'Monthly sales CSV', d: 'Monthly revenue with month-over-month and year-over-year growth.', f: false },
  { kind: 'dashboard', ext: 'csv', t: 'Dashboard trend CSV', d: 'The trend series for the current dashboard filters.', f: true },
] as const

export default function Reports() {
  const { dataset, filters, target, reset } = useWorkspace()
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  if (!dataset || dataset.status !== 'ready') return <><PageHead step="Step G" title="Reports" /><NeedsData /></>
  const go = async (kind: string, ext: 'csv' | 'html', useFilters: boolean) => {
    const name = `${kind}-${dataset.id}.${ext}`
    setBusy(name); setErr(null)
    try { await download(reportUrl(dataset.id, kind, ext, { target, filters: useFilters ? filters : undefined }), name) }
    catch (e: any) { setErr(e.message) } finally { setBusy(null) }
  }
  return (
    <>
      <PageHead step="Step G" title="Reports" lead="Everything you see can leave the app. Files are generated on demand from the same results shown on screen." />
      {err && <ErrorState message={err} />}
      <div className="grid g2">
        {ITEMS.map((i) => {
          const name = `${i.kind}-${dataset.id}.${i.ext}`
          return (
            <Card key={i.kind + i.ext} title={i.t} sub={i.d}>
              <button className="btn btn-primary" disabled={busy === name} onClick={() => go(i.kind, i.ext, i.f)}>{busy === name ? 'Preparing…' : `Download .${i.ext}`}</button>
            </Card>
          )
        })}
      </div>
      <div style={{ marginTop: 16 }}>
        <Note>Forecast files use the measure chosen in the Forecasting Lab ({target.replace('_', ' ')}). HTML reports draw charts with Plotly from a CDN, so open them while online; their tables work offline.</Note>
      </div>
      <Card title="Reset analysis" sub="Clears cached results and, for uploads, removes your file from server memory. You return to the demo dataset.">
        <button className="btn" onClick={reset}>Reset analysis</button>
      </Card>
    </>
  )
}
