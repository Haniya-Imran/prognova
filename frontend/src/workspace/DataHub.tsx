/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useWorkspace } from '../state/Workspace'
import { api, type Mapping } from '../lib/api'
import { Badge, Card, Empty, ErrorState, Info, Loading, Note, PageHead, Segmented } from '../components/ui'
import { num } from '../lib/format'

const ROLES: { key: keyof Mapping; label: string; help: string }[] = [
  { key: 'date', label: 'Date *', help: 'When the sale happened. Required.' },
  { key: 'revenue', label: 'Revenue / sales amount', help: 'Money value of each row. Leave empty if you map quantity and unit price instead.' },
  { key: 'quantity', label: 'Quantity', help: 'Units sold on each row.' },
  { key: 'unit_price', label: 'Unit price', help: 'Price of one unit. Revenue = quantity × unit price when no revenue column exists.' },
  { key: 'order_id', label: 'Order / invoice ID', help: 'Lets the app count orders and average order value.' },
  { key: 'product', label: 'Product', help: 'Product name or code.' },
  { key: 'category', label: 'Category', help: 'Product category or department.' },
  { key: 'region', label: 'Region / country', help: 'Where the sale happened or the customer is.' },
  { key: 'store', label: 'Store / branch', help: 'Shop, branch or outlet.' },
  { key: 'customer', label: 'Customer ID', help: 'Used to count distinct customers.' },
]

function Preview({ rows, columns }: { rows: Record<string, any>[]; columns: string[] }) {
  if (!rows?.length) return <Empty title="No rows to show" />
  return (
    <div className="table-wrap" style={{ maxHeight: 420 }}>
      <table className="tbl">
        <thead><tr>{columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => <tr key={i}>{columns.map((c) => <td key={c} className="clip" title={String(r[c] ?? '')}>{String(r[c] ?? '')}</td>)}</tr>)}</tbody>
      </table>
    </div>
  )
}

function CleanTable({ id }: { id: string }) {
  const [table, setTable] = useState<'sales' | 'returns'>('sales')
  const [page, setPage] = useState(1)
  const [data, setData] = useState<any>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { setErr(null); api.rows(id, page, 25, table).then(setData).catch((e) => setErr(e.message)) }, [id, page, table])
  return (
    <Card title="Cleaned data" sub="The canonical table every later step uses. Returns are kept in their own table."
      actions={<Segmented label="Table" value={table} onChange={(v) => { setTable(v); setPage(1) }} options={[{ value: 'sales', label: 'Sales' }, { value: 'returns', label: 'Returns' }]} />}>
      {err && <ErrorState message={err} />}
      {!data && !err && <Loading rows={2} />}
      {data && <>
        <Preview rows={data.rows} columns={data.columns} />
        <div className="row" style={{ justifyContent: 'space-between', marginTop: 12 }}>
          <span className="muted small">Page {num(data.page)} of {num(data.pages)} · {num(data.total)} rows</span>
          <div className="row">
            <button className="btn btn-sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
            <button className="btn btn-sm" disabled={page >= data.pages} onClick={() => setPage(page + 1)}>Next</button>
          </div>
        </div>
      </>}
    </Card>
  )
}

export default function DataHub() {
  const { dataset, upload, prepare, openSample, reset } = useWorkspace()
  const nav = useNavigate()
  const fileRef = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [errDetails, setErrDetails] = useState<string[] | null>(null)
  const [mapping, setMapping] = useState<Mapping>({})
  const [opts, setOpts] = useState({ drop_duplicates: true, separate_returns: true, cancellation_prefix: '' })
  const [check, setCheck] = useState<any>(null)

  useEffect(() => { if (dataset?.status === 'needs_mapping') setMapping(dataset.detection?.mapping || {}); setCheck(null) }, [dataset?.id, dataset?.status, dataset?.detection])

  async function onFile(f: File | undefined) {
    if (!f) return
    setErr(null); setErrDetails(null); setBusy(`Reading ${f.name}…`)
    try { await upload(f) } catch (e: any) { setErr(e.message) } finally { setBusy(null) }
  }
  async function onPrepare() {
    setErr(null); setErrDetails(null); setBusy('Cleaning and preparing your data…')
    try { await prepare(mapping, { ...opts, cancellation_prefix: opts.cancellation_prefix || null }); nav('/app/quality') }
    catch (e: any) { setErr(e.message); setErrDetails(Array.isArray(e.details) ? e.details.map((d: any) => typeof d === 'string' ? d : d.detail || JSON.stringify(d)) : null) }
    finally { setBusy(null) }
  }
  async function onCheck() {
    if (!dataset) return
    setErr(null); setErrDetails(null); setBusy('Checking quality…')
    try { setCheck(await api.qualityCheck(dataset.id, mapping)) }
    catch (e: any) { setErr(e.message); setErrDetails(Array.isArray(e.details) ? e.details : null) } finally { setBusy(null) }
  }

  const det = dataset?.detection
  return (
    <>
      <PageHead step="Step A" title="Data Hub"
        lead="Start with the real demo dataset, or upload your own sales CSV. Nothing is stored on disk — your file lives in server memory for this session only."
        actions={dataset && dataset.source === 'upload' ? <button className="btn" onClick={reset}>Reset & go back to demo data</button> : undefined} />

      <div className="grid g2">
        <Card title="Demo dataset (real)" sub="UCI Online Retail II · CC BY 4.0">
          <p className="small" style={{ marginBottom: 12 }}>Every transaction of a UK online giftware shop, Dec 2009 – Dec 2011: over 1 million rows, 43 countries, ~4,900 products. Already cleaned and ready.</p>
          <button className="btn btn-primary" onClick={async () => { setErr(null); await openSample() }} disabled={dataset?.source === 'sample'}>
            {dataset?.source === 'sample' ? 'In use' : 'Use demo dataset'}
          </button>
        </Card>
        <Card title="Upload your own CSV" sub="Up to 4 MB / 200,000 rows. Needs a date column and a sales value (or quantity + price).">
          <div className={`drop ${over ? 'over' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)}
            onDrop={(e) => { e.preventDefault(); setOver(false); onFile(e.dataTransfer.files?.[0]) }}>
            <p style={{ marginBottom: 10 }}>Drag a .csv file here, or</p>
            <button className="btn" onClick={() => fileRef.current?.click()} disabled={!!busy}>Choose file</button>
            <input ref={fileRef} type="file" accept=".csv,.txt,.tsv,text/csv" hidden onChange={(e) => { onFile(e.target.files?.[0]); e.target.value = '' }} aria-label="Upload CSV file" />
          </div>
        </Card>
      </div>

      {busy && <div style={{ marginTop: 16 }}><Loading label={busy} rows={1} /></div>}
      {err && <div style={{ marginTop: 16 }}><ErrorState message={err} />{errDetails && <ul className="small">{errDetails.map((d, i) => <li key={i}>{d}</li>)}</ul>}</div>}

      {dataset?.status === 'needs_mapping' && det && (
        <div className="stack" style={{ marginTop: 16 }}>
          <Card title="Step 2 · Match your columns" sub={`Read ${num(dataset.read_info?.rows)} rows × ${dataset.read_info?.columns} columns (separator "${dataset.read_info?.delimiter === '\t' ? 'tab' : dataset.read_info?.delimiter}", ${dataset.read_info?.encoding}). We guessed each column's role — check them.`}>
            {dataset.read_info?.skipped_bad_lines > 0 && <Note tone="warn">{dataset.read_info.skipped_bad_lines} malformed line(s) were skipped while reading.</Note>}
            {dataset.read_info?.truncated_to_rows && <Note tone="warn">Only the first {num(dataset.read_info.truncated_to_rows)} rows were kept (upload limit).</Note>}
            {det.uncertain_roles?.length > 0 && <Note>Please double-check: {det.uncertain_roles.join(', ')} (low-confidence guesses).</Note>}
            <div className="grid g3" style={{ marginTop: 12 }}>
              {ROLES.map((r) => (
                <label className="field" key={r.key}>
                  <span>{r.label}<Info text={r.help} />{det.confidence?.[r.key] !== undefined && mapping[r.key] === det.mapping[r.key] && (
                    <Badge tone={det.confidence[r.key] >= 0.75 ? 'good' : 'warn'}>{det.confidence[r.key] >= 0.75 ? 'auto' : 'check'}</Badge>)}</span>
                  <select className="input" aria-label={r.label.replace(' *', '')} value={mapping[r.key] || ''} onChange={(e) => setMapping({ ...mapping, [r.key]: e.target.value || null })}>
                    <option value="">— not available —</option>
                    {dataset.raw_columns.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                </label>
              ))}
            </div>
            <h4 style={{ margin: '18px 0 8px', fontSize: 14 }}>Cleaning choices</h4>
            <div className="grid g3">
              <label className="check"><input type="checkbox" checked={opts.drop_duplicates} onChange={(e) => setOpts({ ...opts, drop_duplicates: e.target.checked })} />
                <span>Remove exact duplicate rows<br /><span className="muted small">Rows identical in every column are counted once.</span></span></label>
              <label className="check"><input type="checkbox" checked={opts.separate_returns} onChange={(e) => setOpts({ ...opts, separate_returns: e.target.checked })} />
                <span>Treat negative rows as returns<br /><span className="muted small">Kept in a separate returns table, not mixed into sales.</span></span></label>
              <label className="field"><span>Cancelled-order prefix (optional)<Info text='If cancelled order IDs start with a letter, e.g. "C123", enter C.' /></span>
                <input className="input" aria-label="Cancelled-order prefix" maxLength={5} value={opts.cancellation_prefix} onChange={(e) => setOpts({ ...opts, cancellation_prefix: e.target.value })} placeholder="e.g. C" /></label>
            </div>
            <div className="row" style={{ marginTop: 18 }}>
              <button className="btn" onClick={onCheck} disabled={!!busy}>Preview quality report</button>
              <button className="btn btn-primary" onClick={onPrepare} disabled={!!busy}>Prepare data →</button>
            </div>
            {check && (
              <div className="kpis" style={{ marginTop: 16 }}>
                <div className="kpi"><span className="kpi-label">Rows</span><strong className="kpi-value">{num(check.rows)}</strong></div>
                <div className="kpi"><span className="kpi-label">Duplicate rows</span><strong className="kpi-value">{num(check.duplicate_rows)}</strong></div>
                <div className="kpi"><span className="kpi-label">Unreadable dates</span><strong className="kpi-value">{num(check.unparseable_dates)}</strong></div>
                <div className="kpi"><span className="kpi-label">Negative values</span><strong className="kpi-value">{num(check.negative_value_rows)}</strong></div>
                <div className="kpi"><span className="kpi-label">Frequency</span><strong className="small-val">{check.frequency?.frequency} · {check.date_min?.slice(0, 10)} → {check.date_max?.slice(0, 10)}</strong></div>
              </div>
            )}
          </Card>
          <Card title="File preview" sub="First 20 rows exactly as uploaded."><Preview rows={dataset.preview || []} columns={dataset.raw_columns} /></Card>
        </div>
      )}

      {dataset?.status === 'ready' && (
        <div className="stack" style={{ marginTop: 16 }}>
          <Card title="Current dataset" sub={dataset.meta?.description}>
            <div className="grid g3 small">
              <div><b>Rows after cleaning</b><br />{num(dataset.rows)} sales · {num(dataset.return_rows)} returns</div>
              <div><b>Date range</b><br />{dataset.date_min} → {dataset.date_max}</div>
              <div><b>Records arrive</b><br />{dataset.frequency?.frequency || '—'} ({num(dataset.frequency?.distinct_dates)} distinct days)</div>
              <div><b>Column roles</b><br />{Object.entries(dataset.mapping || {}).filter(([, v]) => v).map(([k, v]) => `${k} ← ${v}`).join(' · ')}</div>
              <div><b>Dimensions</b><br />{Object.entries(dataset.dimensions || {}).filter(([, v]) => v).map(([k]) => k).join(', ') || 'none'}</div>
              {dataset.meta?.license && <div><b>License</b><br />{dataset.meta.license}</div>}
            </div>
            {dataset.meta?.limitations?.length > 0 && (
              <><h4 style={{ margin: '16px 0 6px', fontSize: 14 }}>Known limitations</h4>
                <ul className="small" style={{ margin: 0, paddingLeft: 18 }}>{dataset.meta.limitations.map((l: string) => <li key={l}>{l}</li>)}</ul></>
            )}
          </Card>
          {dataset.preview && dataset.preview.length > 0 && <Card title="Raw file preview" sub="First rows of the original file, before cleaning."><Preview rows={dataset.preview} columns={dataset.raw_columns} /></Card>}
          <CleanTable id={dataset.id} />
        </div>
      )}
    </>
  )
}
