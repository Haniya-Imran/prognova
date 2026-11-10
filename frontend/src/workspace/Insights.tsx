/* eslint-disable @typescript-eslint/no-explicit-any */
import { useWorkspace } from '../state/Workspace'
import { api } from '../lib/api'
import { useLoad } from '../lib/useLoad'
import { Badge, ErrorState, Loading, Note, PageHead, Segmented } from '../components/ui'
import { NeedsData } from './Quality'

const TYPE: Record<string, string> = { trend: 'Trend', seasonality: 'Seasonality', pattern: 'Pattern', risk: 'Risk', region: 'Regions', product: 'Products', returns: 'Returns', forecast: 'Forecast' }

export default function Insights() {
  const { dataset, target, setTarget } = useWorkspace()
  const ready = dataset?.status === 'ready'
  const { data, error, loading, retry } = useLoad(ready ? () => api.insights(dataset!.id, target) : null, [dataset?.id, ready, target])
  if (!ready) return <><PageHead step="Step F" title="Business Insights" /><NeedsData /></>
  return (
    <>
      <PageHead step="Step F" title="Business Insights"
        lead="Findings written from the actual numbers. Each one shows its evidence; suggested actions state the assumption they rely on."
        actions={<Segmented label="Forecast measure" value={target} onChange={setTarget} options={[{ value: 'net_revenue', label: 'Net revenue' }, { value: 'gross_revenue', label: 'Gross' }, { value: 'units', label: 'Units', disabled: !dataset!.available?.quantity }]} />} />
      {loading && !data && <Loading label="Reading the analysis and forecast…" rows={4} />}
      {error && <ErrorState message={error} onRetry={retry} />}
      {data && (
        <div className="stack" style={{ opacity: loading ? .6 : 1 }}>
          {data.forecast_status !== 'ok' && <Note tone="warn">No forecast insight: {data.forecast_error?.message || 'the forecast could not run.'}</Note>}
          {data.insights.map((i: any) => (
            <article key={i.id} className={`insight ${i.severity}`}>
              <div className="bar" aria-hidden />
              <div>
                <div className="row" style={{ gap: 8, marginBottom: 4 }}><Badge tone={i.severity === 'positive' ? 'good' : i.severity === 'warning' ? 'warn' : 'brand'}>{TYPE[i.type] || i.type}</Badge></div>
                <h4>{i.title}</h4>
                <p>{i.detail}</p>
                {i.recommendation && <div className="act"><b>Suggested action:</b> {i.recommendation}</div>}
                {i.assumption && <p className="ass">Assumption: {i.assumption}</p>}
              </div>
            </article>
          ))}
          <Note>Revenue here means sales value. Profit is not calculated because the data has no cost information. Forecasts are estimates, not guarantees of demand.</Note>
        </div>
      )}
    </>
  )
}
