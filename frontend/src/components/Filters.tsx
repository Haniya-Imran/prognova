import { useEffect, useId, useRef, useState } from 'react'
import { api, type Filters } from '../lib/api'
import { useWorkspace } from '../state/Workspace'
import { compact } from '../lib/format'

type Dim = 'product' | 'category' | 'region' | 'store'
const LABELS: Record<Dim, string> = { product: 'Products', category: 'Categories', region: 'Regions / countries', store: 'Stores' }

export function MultiSelect({ dim, value, onChange }: { dim: Dim; value: string[]; onChange: (v: string[]) => void }) {
  const { dataset } = useWorkspace()
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const [opts, setOpts] = useState<{ value: string; revenue: number }[]>([])
  const [active, setActive] = useState(0)
  const [loading, setLoading] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  const id = useId()

  useEffect(() => {
    if (!open || !dataset) return
    let alive = true
    setLoading(true)
    const t = setTimeout(() => {
      api.dimension(dataset.id, dim, q, 40).then((r) => { if (alive) { setOpts(r.values); setActive(0) } })
        .catch(() => alive && setOpts([])).finally(() => alive && setLoading(false))
    }, 180)
    return () => { alive = false; clearTimeout(t) }
  }, [q, open, dim, dataset])

  useEffect(() => {
    const close = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  const choices = opts.filter((o) => !value.includes(o.value))
  const pick = (v: string) => { onChange([...value, v]); setQ('') }

  return (
    <div className="field ms" ref={box}>
      <span id={`${id}-l`}>{LABELS[dim]}</span>
      <div className="ms-box" onClick={() => setOpen(true)}>
        {value.map((v) => (
          <span className="chip" key={v} title={v}><span>{v}</span>
            <button type="button" aria-label={`Remove ${v}`} onClick={(e) => { e.stopPropagation(); onChange(value.filter((x) => x !== v)) }}>×</button>
          </span>
        ))}
        <input
          aria-labelledby={`${id}-l`} role="combobox" aria-expanded={open} aria-controls={`${id}-list`} aria-autocomplete="list"
          placeholder={value.length ? '' : 'All — type to search'} value={q}
          onChange={(e) => { setQ(e.target.value); setOpen(true) }} onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); setActive((a) => Math.min(a + 1, choices.length - 1)) }
            else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)) }
            else if (e.key === 'Enter' && open && choices[active]) { e.preventDefault(); pick(choices[active].value) }
            else if (e.key === 'Escape') setOpen(false)
            else if (e.key === 'Backspace' && !q && value.length) onChange(value.slice(0, -1))
          }}
        />
      </div>
      {open && (
        <ul className="ms-list" role="listbox" id={`${id}-list`}>
          {loading && !choices.length && <li aria-disabled>Searching…</li>}
          {!loading && !choices.length && <li aria-disabled>No matches</li>}
          {choices.map((o, i) => (
            <li key={o.value} role="option" aria-selected={i === active} onMouseDown={(e) => { e.preventDefault(); pick(o.value) }}>
              <span>{o.value}</span><small>{compact(o.revenue)}</small>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function FilterBar({ filters, onChange, onReset, showDims = true }: {
  filters: Filters; onChange: (f: Filters) => void; onReset: () => void; showDims?: boolean
}) {
  const { dataset } = useWorkspace()
  const dims = (['region', 'category', 'store', 'product'] as Dim[]).filter((d) => dataset?.dimensions?.[d])
  const active = !!(filters.start || filters.end || dims.some((d) => filters[d].length))
  return (
    <div className="filterbar">
      <label className="field"><span>From</span>
        <input className="input" type="date" value={filters.start || ''} min={dataset?.date_min} max={filters.end || dataset?.date_max}
          onChange={(e) => onChange({ ...filters, start: e.target.value || null })} />
      </label>
      <label className="field"><span>To</span>
        <input className="input" type="date" value={filters.end || ''} min={filters.start || dataset?.date_min} max={dataset?.date_max}
          onChange={(e) => onChange({ ...filters, end: e.target.value || null })} />
      </label>
      {showDims && dims.map((d) => <MultiSelect key={d} dim={d} value={filters[d]} onChange={(v) => onChange({ ...filters, [d]: v })} />)}
      <div className="field"><span aria-hidden>&nbsp;</span>
        <button className="btn" type="button" onClick={onReset} disabled={!active}>Clear filters</button>
      </div>
    </div>
  )
}
