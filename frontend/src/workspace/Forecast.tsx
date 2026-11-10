/* eslint-disable @typescript-eslint/no-explicit-any */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useWorkspace } from '../state/Workspace'
import { api, download, emptyFilters, reportUrl, waitForJob, type Filters, type Job, type Target } from '../lib/api'
import { Badge, Card, ErrorState, Info, Kpi, Loading, Note, PageHead, Segmented } from '../components/ui'
import { MultiSelect } from '../components/Filters'
import { alpha, Chart, palette } from '../components/Chart'
import { money, monthLabel, num, pct } from '../lib/format'
import { NeedsData } from './Quality'

export default function Forecast() {
  const { dataset, target, setTarget, cur } = useWorkspace()
  const ready = dataset?.status === 'ready'
  const [seg, setSeg] = useState<Filters>(emptyFilters())
  const [job, setJob] = useState<Job | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [h, setH] = useState(1)
  const cancel = useRef({ cancelled: false })
  const P = palette()

  const run = useCallback(async (t: Target, f: Filters) => {
    if (!dataset) return
    cancel.current.cancelled = true
    const token = { cancelled: false }
    cancel.current = token
    setErr(null)
    try {
      const j = await api.runForecast(dataset.id, t, f)
      const done = await waitForJob(j, (x) => { if (!token.cancelled) setJob(x) }, token)
      if (!token.cancelled && done.status === 'failed') setErr(done.error?.message || 'Forecast failed.')
    } catch (e: any) { if (!token.cancelled) setErr(e.message) }
  }, [dataset])

  useEffect(() => { if (ready) run(target, seg) ; return () => { cancel.current.cancelled = true } // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, dataset?.id])

  if (!ready) return <><PageHead step="Step E" title="Forecasting Lab" /><NeedsData /></>
  const r = job?.status === 'done' ? job.result : null
  const busy = job && (job.status === 'queued' || job.status === 'running')
  const unitsOk = !!dataset!.available?.quantity
  const isMoney = (r?.target || target) !== 'units'
  const fmt = (v: number) => isMoney ? money(v, cur) : num(v)
  const segDims = (['region', 'category', 'store', 'product'] as const).filter((d) => dataset!.dimensions?.[d])

  async function dl(kind: string, ext: 'csv' | 'html') {
    try { await download(reportUrl(dataset!.id, kind, ext, { target, filters: seg }), `${kind}-${target}.${ext}`) } catch (e: any) { setErr(e.message) }
  }

  return (
    <>
      <PageHead step="Step E" title="Forecasting Lab"
        lead="Several models are tested on past months they never saw. The one with the smallest real error forecasts the next 3 calendar months, with a range showing how uncertain that is."
        actions={r && <><button className="btn" onClick={() => dl('forecast', 'csv')}>Forecast CSV</button><button className="btn" onClick={() => dl('backtest', 'csv')}>Backtest CSV</button><button className="btn btn-primary" onClick={() => dl('forecast', 'html')}>Forecast report</button></>} />

      <Card title="What to forecast">
        <div className="filterbar">
          <div className="field measure-field"><span>Measure<Info text="Net revenue subtracts returns and cancellations. Units counts items sold." /></span>
            <Segmented label="Forecast target" value={target} onChange={setTarget} options={[
              { value: 'net_revenue', label: 'Net revenue' }, { value: 'gross_revenue', label: 'Gross revenue' }, { value: 'units', label: 'Units', disabled: !unitsOk }]} /></div>
          {segDims.filter((d) => d !== 'product').map((d) => <MultiSelect key={d} dim={d} value={seg[d]} onChange={(v) => setSeg({ ...seg, [d]: v })} />)}
          {segDims.includes('product') && <MultiSelect dim="product" value={seg.product} onChange={(v) => setSeg({ ...seg, product: v })} />}
          <div className="field"><span aria-hidden>&nbsp;</span><button className="btn btn-primary" onClick={() => run(target, seg)} disabled={!!busy}>{busy ? 'Running…' : 'Run forecast'}</button></div>
        </div>
        <p className="small muted" style={{ marginTop: 10 }}>Leave segments empty to forecast the whole business. The model always learns from all available history; date filters do not apply here.</p>
      </Card>

      {busy && <div style={{ marginTop: 16 }}><Loading label={`${job!.stage}… ${job!.elapsed_seconds}s`} rows={2} /></div>}
      {err && <div style={{ marginTop: 16 }}><ErrorState message={err} onRetry={() => run(target, seg)} /></div>}

      {r && (
        <div className="stack" style={{ marginTop: 16 }}>
          <div className="kpis">
            <Kpi tone="brand" label={`Next ${r.horizon_months} months total`} value={fmt(r.summary.total)} deltaLabel={`80% range ${fmt(r.summary.total_lower_80)} – ${fmt(r.summary.total_upper_80)}`} />
            <Kpi label="vs same months last year" value={pct(r.summary.change_vs_last_year_pct)} delta={r.summary.change_vs_last_year_pct} deltaLabel={r.summary.same_period_last_year != null ? `last year: ${fmt(r.summary.same_period_last_year)}` : 'no comparable year'} />
            <Kpi label="vs last 3 months" value={pct(r.summary.change_vs_last_3_months_pct)} delta={r.summary.change_vs_last_3_months_pct} deltaLabel={`last 3 months: ${fmt(r.summary.last_3_months_actual)}`} />
            <Kpi label="Selected model" value={<span className="small-val">{r.selected.name}</span>} deltaLabel={`backtest error (WAPE) ${num(r.selected.metrics.wape, 1)}%`} info="WAPE = total absolute error ÷ total actual sales, across all backtest months. 10% means forecasts were off by about a tenth." />
          </div>

          <Card title={`${r.target_label}: history and next ${r.horizon_months} months`} sub={`Trained on complete months through ${r.trained_through}. Shaded bands: 80% and 95% ranges.`}>
            <Chart ariaLabel="Historical sales and forecast with prediction intervals" height={380} data={(() => {
              const hx = r.history.map((x: any) => x.month), hy = r.history.map((x: any) => x.value)
              const fx = r.forecast.map((x: any) => x.month)
              const lastX = hx[hx.length - 1], lastY = hy[hy.length - 1]
              const band = (lo: string, hi: string, color: string, name: string) => [
                { type: 'scatter', mode: 'lines', x: [lastX, ...fx], y: [lastY, ...r.forecast.map((x: any) => x[hi])], line: { width: 0 }, hoverinfo: 'skip', showlegend: false },
                { type: 'scatter', mode: 'lines', x: [lastX, ...fx], y: [lastY, ...r.forecast.map((x: any) => x[lo])], line: { width: 0 }, fill: 'tonexty', fillcolor: color, name, hoverinfo: 'skip' }]
              return [
                ...band('lower_95', 'upper_95', alpha(P[1], .14), '95% range'),
                ...band('lower_80', 'upper_80', alpha(P[1], .30), '80% range'),
                { type: 'scatter', mode: 'lines+markers', x: hx, y: hy, name: 'Actual', line: { color: P[0], width: 2.5 }, marker: { size: 5 }, hovertemplate: `%{x|%b %Y}<br>Actual ${isMoney ? cur : ''}%{y:,.0f}<extra></extra>` },
                { type: 'scatter', mode: 'lines+markers', x: [lastX, ...fx], y: [lastY, ...r.forecast.map((x: any) => x.forecast)], name: 'Forecast', line: { color: P[1], width: 3, dash: 'dash' }, marker: { size: 8, symbol: 'diamond' }, hovertemplate: `%{x|%b %Y}<br>Forecast ${isMoney ? cur : ''}%{y:,.0f}<extra></extra>` },
              ]
            })()} layout={{ yaxis: { tickprefix: isMoney ? cur : '' }, xaxis: { type: 'date', tickformat: '%b %y' }, hovermode: 'x unified' }} />
            <div className="table-wrap" style={{ marginTop: 10 }}><table className="tbl">
              <thead><tr><th>Month</th><th className="n">Forecast</th><th className="n">80% range</th><th className="n">95% range</th><th className="n">Same month last year</th><th className="n">Change</th></tr></thead>
              <tbody>{r.forecast.map((x: any) => <tr key={x.month}><td><b>{x.label}</b></td><td className="n"><b>{fmt(x.forecast)}</b></td><td className="n">{fmt(x.lower_80)} – {fmt(x.upper_80)}</td><td className="n">{fmt(x.lower_95)} – {fmt(x.upper_95)}</td><td className="n">{x.same_month_last_year != null ? fmt(x.same_month_last_year) : '—'}</td><td className="n">{pct(x.change_vs_last_year_pct)}</td></tr>)}
                <tr><td><b>Total</b></td><td className="n"><b>{fmt(r.summary.total)}</b></td><td className="n">{fmt(r.summary.total_lower_80)} – {fmt(r.summary.total_upper_80)}</td><td /><td className="n">{r.summary.same_period_last_year != null ? fmt(r.summary.same_period_last_year) : '—'}</td><td className="n">{pct(r.summary.change_vs_last_year_pct)}</td></tr></tbody>
            </table></div>
            <p className="small muted" style={{ marginTop: 10 }}>{r.frequency_note}</p>
          </Card>

          <div className="grid g2">
            <Card title="Why this model" sub={r.selected.description}>
              <p>{r.selected.reason}</p>
              <div className="grid g2 small" style={{ marginTop: 12 }}>
                <div><b>MAE</b> <Info text="Average size of the monthly miss, in the same units as sales." /><br />{fmt(r.selected.metrics.mae)}</div>
                <div><b>RMSE</b> <Info text="Like MAE but punishes big misses more." /><br />{fmt(r.selected.metrics.rmse)}</div>
                <div><b>WAPE</b><br />{num(r.selected.metrics.wape, 2)}%</div>
                <div><b>sMAPE</b> <Info text="Symmetric percentage error per month, averaged." /><br />{num(r.selected.metrics.smape, 2)}%</div>
                <div><b>MAPE</b><br />{r.selected.metrics.mape != null ? `${num(r.selected.metrics.mape, 2)}%` : r.selected.metrics.mape_note}</div>
                <div><b>Bias</b> <Info text="Positive = forecasts were too high on average; negative = too low." /><br />{pct(r.selected.metrics.bias_pct)}</div>
              </div>
              <Note>{r.backtest.method} Windows: {r.backtest.folds}, origins {monthLabel(r.backtest.first_origin)} → {monthLabel(r.backtest.last_origin)}. No random splits, no peeking at the future.</Note>
            </Card>
            <Card title="Model comparison" sub="Lower WAPE = more accurate on months the model had not seen.">
              <Chart ariaLabel="Backtest WAPE by model" height={260} data={[(() => {
                const ok = r.candidates.filter((c: any) => c.metrics).sort((a: any, b: any) => b.metrics.wape - a.metrics.wape)
                return { type: 'bar', orientation: 'h', y: ok.map((c: any) => c.name), x: ok.map((c: any) => c.metrics.wape), marker: { color: ok.map((c: any) => c.selected ? P[1] : c.family === 'Baseline' ? '#5b6a8f' : P[0]) }, text: ok.map((c: any) => `${c.metrics.wape.toFixed(1)}%`), textposition: 'outside', hovertemplate: '%{y}: %{x:.2f}% WAPE<extra></extra>', cliponaxis: false }
              })()]} layout={{ margin: { l: 230, r: 40, t: 6, b: 36 }, xaxis: { ticksuffix: '%' } }} />
              <div className="table-wrap" style={{ marginTop: 8 }}><table className="tbl"><thead><tr><th>Model</th><th>Type</th><th className="n">WAPE</th><th className="n">MAE</th><th>Status</th></tr></thead>
                <tbody>{r.candidates.map((c: any) => <tr key={c.key} className={c.selected ? 'sel' : ''}><td title={c.description}>{c.name}</td><td>{c.family}</td>
                  <td className="n">{c.metrics ? `${num(c.metrics.wape, 1)}%` : '—'}</td><td className="n">{c.metrics ? fmt(c.metrics.mae) : '—'}</td>
                  <td>{c.selected ? <Badge tone="good">Selected</Badge> : c.eligible ? <Badge>#{c.rank}</Badge> : <span className="small muted">{c.reason}</span>}</td></tr>)}
                  {r.not_used.map((n: any) => <tr key={n.name}><td>{n.name}</td><td>—</td><td className="n">—</td><td className="n">—</td><td className="small muted">{n.reason}</td></tr>)}</tbody></table></div>
            </Card>
          </div>

          <Card title="Backtest: actual vs predicted" sub="What the selected model would have predicted at each past origin, against what really happened."
            actions={<Segmented label="Forecast horizon" value={String(h)} onChange={(v) => setH(Number(v))} options={[1, 2, 3].map((x) => ({ value: String(x), label: `${x} month${x > 1 ? 's' : ''} ahead` }))} />}>
            {(() => {
              const v = r.validation.filter((x: any) => x.horizon === h)
              return <Chart ariaLabel="Backtest actual versus predicted" height={320} data={[
                { type: 'bar', x: v.map((x: any) => x.month), y: v.map((x: any) => x.actual), name: 'Actual', marker: { color: P[0] }, hovertemplate: `%{x|%b %Y}<br>Actual ${isMoney ? cur : ''}%{y:,.0f}<extra></extra>` },
                { type: 'scatter', mode: 'lines+markers', x: v.map((x: any) => x.month), y: v.map((x: any) => x.predicted), name: 'Predicted', line: { color: P[1], width: 3 }, marker: { size: 9 }, hovertemplate: `%{x|%b %Y}<br>Predicted ${isMoney ? cur : ''}%{y:,.0f}<extra></extra>` }]}
                layout={{ yaxis: { tickprefix: isMoney ? cur : '' }, xaxis: { type: 'date', tickformat: '%b %y' }, barmode: 'overlay' }} />
            })()}
            {r.interval_backtest_coverage_80_pct != null && <p className="small muted">{r.interval_method} In the backtest, {num(r.interval_backtest_coverage_80_pct, 0)}% of real months fell inside the 80% range.</p>}
          </Card>

          <Card title="Limitations — please read">
            <ul style={{ margin: 0, paddingLeft: 18 }}>{r.limitations.map((l: string) => <li key={l} style={{ marginBottom: 4 }}>{l}</li>)}</ul>
          </Card>
        </div>
      )}
    </>
  )
}
