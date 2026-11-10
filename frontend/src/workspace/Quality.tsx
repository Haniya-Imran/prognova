/* eslint-disable @typescript-eslint/no-explicit-any */
import { Link } from 'react-router-dom'
import { useWorkspace } from '../state/Workspace'
import { Badge, Card, Kpi, Note, PageHead } from '../components/ui'
import { Chart, palette } from '../components/Chart'
import { money, num } from '../lib/format'

export function NeedsData() {
  return <Note tone="warn">Prepare a dataset first in the <Link to="/app/data">Data Hub</Link>.</Note>
}

export default function Quality() {
  const { dataset, cur } = useWorkspace()
  if (!dataset || dataset.status !== 'ready') return <><PageHead step="Step B" title="Data Quality & Preparation" /><NeedsData /></>
  const q = dataset.quality
  const P = palette()
  const missing = (q.missing as any[]).filter((m) => m.missing > 0)
  return (
    <>
      <PageHead step="Step B" title="Data Quality & Preparation"
        lead="What the raw file looked like, and exactly what was changed to make it trustworthy. Nothing is hidden: every rule and the rows it touched are listed." />
      <div className="kpis">
        <Kpi label="Raw rows" value={num(q.rows)} deltaLabel={`${q.columns} columns`} />
        <Kpi label="Exact duplicates" value={num(q.duplicate_rows)} deltaLabel={`${((q.duplicate_rows / q.rows) * 100).toFixed(2)}% of rows`} />
        <Kpi label="Negative-value rows" value={num(q.negative_value_rows)} deltaLabel="returns / cancellations" info="Rows with a negative quantity or amount. They are kept as returns, not deleted." />
        <Kpi label="Unreadable dates" value={num(q.unparseable_dates)} deltaLabel={q.unparseable_dates ? 'rows dropped' : 'all dates parsed'} />
        <Kpi label="Clean sales lines" value={num(dataset.rows)} tone="brand" deltaLabel={`${((dataset.rows! / q.rows) * 100).toFixed(1)}% of raw rows kept`} />
      </div>

      <div className="grid g2" style={{ marginTop: 16 }}>
        <Card title="Cleaning log" sub="Applied in this order. Counts are rows affected.">
          <ol className="steps">
            {dataset.steps!.map((s, i) => (
              <li key={i}><span className="dot">{i + 1}</span><div><b>{s.step}</b><p>{s.detail}</p></div>
                <Badge tone={s.rows_affected && !['Loaded', 'Ready for analysis'].includes(s.step) ? 'warn' : 'neutral'}>{num(s.rows_affected)}</Badge></li>
            ))}
          </ol>
        </Card>
        <div className="stack">
          <Card title="Missing values by column" sub={missing.length ? 'Share of empty cells in the raw file.' : 'No empty cells in any column.'}>
            {missing.length > 0 && (
              <Chart ariaLabel="Missing values by column" height={Math.max(160, missing.length * 38 + 50)}
                data={[{ type: 'bar', orientation: 'h', y: missing.map((m) => m.column), x: missing.map((m) => m.pct), marker: { color: P[1] },
                  text: missing.map((m) => `${num(m.missing)} (${m.pct}%)`), textposition: 'auto', hovertemplate: '%{y}: %{x:.2f}% missing<extra></extra>' }]}
                layout={{ xaxis: { ticksuffix: '%', title: { text: 'Missing %' } }, margin: { l: 110, r: 16, t: 8, b: 44 } }} />
            )}
          </Card>
          <Card title="Outlier inspection" info="A line is flagged if its value is above Q3 + 3 × IQR (a standard, robust rule). Flagged lines are NOT removed: large wholesale orders are real sales.">
            <div className="grid g2 small">
              <div><b>Rule</b><br />{q.outliers.method}</div>
              <div><b>Threshold</b><br />{money(q.outliers.threshold, cur)}</div>
              <div><b>Flagged lines</b><br />{num(q.outliers.count)} ({q.outliers.pct}%)</div>
              <div><b>Largest / median line</b><br />{money(q.outliers.max_value, cur)} / {money(q.outliers.median_value, cur)}</div>
            </div>
            <p className="small muted" style={{ marginTop: 10 }}>Decision: kept. Very large lines are mostly wholesale orders. The biggest single order in the demo data was cancelled the same day — it appears in Returns, so net revenue cancels it out.</p>
          </Card>
          <Card title="Time coverage">
            <div className="grid g2 small">
              <div><b>First record</b><br />{q.date_min}</div>
              <div><b>Last record</b><br />{q.date_max}</div>
              <div><b>Records arrive</b><br />{q.frequency.frequency} (median gap {q.frequency.median_gap_days} day)</div>
              <div><b>Distinct dates</b><br />{num(q.frequency.distinct_dates)}</div>
            </div>
          </Card>
          <Card title="Column types" sub="How each raw column was read, and the role it plays.">
            <div className="table-wrap"><table className="tbl"><thead><tr><th>Column</th><th>Read as</th><th>Role</th></tr></thead>
              <tbody>{(q.column_types as any[]).map((c) => <tr key={c.column}><td>{c.column}</td><td>{c.inferred}</td><td>{c.role ? <Badge tone="brand">{c.role}</Badge> : <span className="muted">unused</span>}</td></tr>)}</tbody></table></div>
          </Card>
        </div>
      </div>
    </>
  )
}
