import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { api, emptyFilters, setRecovery, type DatasetSummary, type Filters, type Mapping, type Target } from '../lib/api'
import { clearUpload, loadUpload, saveUpload, type CachedUpload } from '../lib/fileCache'

interface WorkspaceState {
  dataset: DatasetSummary | null
  loading: boolean
  error: string | null
  filters: Filters
  setFilters: (f: Filters) => void
  resetFilters: () => void
  target: Target
  setTarget: (t: Target) => void
  openSample: () => Promise<void>
  upload: (file: File) => Promise<DatasetSummary>
  prepare: (mapping: Mapping, options: { drop_duplicates: boolean; separate_returns: boolean; cancellation_prefix?: string | null }) => Promise<void>
  reset: () => Promise<void>
  cur: string
}

const Ctx = createContext<WorkspaceState | null>(null)
const KEY = 'pgn.dataset'

function read<T>(k: string, fallback: T): T {
  try { const v = sessionStorage.getItem(k); return v ? (JSON.parse(v) as T) : fallback } catch { return fallback }
}
function write(k: string, v: unknown) {
  try { if (v === null) sessionStorage.removeItem(k); else sessionStorage.setItem(k, JSON.stringify(v)) } catch { /* storage blocked */ }
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [dataset, setDataset] = useState<DatasetSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFiltersState] = useState<Filters>(() => read('pgn.filters', emptyFilters()))
  const [target, setTargetState] = useState<Target>(() => read('pgn.target', 'net_revenue' as Target))

  const setFilters = useCallback((f: Filters) => { setFiltersState(f); write('pgn.filters', f) }, [])
  const resetFilters = useCallback(() => setFilters(emptyFilters()), [setFilters])
  const setTarget = useCallback((t: Target) => { setTargetState(t); write('pgn.target', t) }, [])

  const openSample = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const d = await api.sample()
      setDataset(d); write(KEY, d.id)
    } catch (e) { setError((e as Error).message) } finally { setLoading(false) }
  }, [])

  const cached = useRef<CachedUpload | null>(null)

  // If the API forgot an uploaded file (serverless restart), re-send it with the same mapping.
  useEffect(() => {
    setRecovery(async (id) => {
      const c = cached.current || (await loadUpload())
      if (!c || c.id !== id) return false
      try {
        const up = await api.upload(c.file)
        if (up.id !== id) return false
        if (c.mapping) await api.prepare(id, c.mapping as Mapping, c.options as { drop_duplicates: boolean; separate_returns: boolean })
        return true
      } catch { return false }
    })
    return () => setRecovery(null)
  }, [])

  // Restore the session's dataset, or open the real sample so the app is usable at once.
  useEffect(() => {
    const saved = read<string | null>(KEY, null)
    if (saved && saved !== 'online-retail-ii') {
      api.dataset(saved).then((d) => { setDataset(d); setLoading(false) }).catch(() => { write(KEY, null); resetFilters(); openSample() })
    } else {
      openSample()
    }
  }, [openSample, resetFilters])

  const upload = useCallback(async (file: File) => {
    const d = await api.upload(file)
    cached.current = { id: d.id, file }
    saveUpload(cached.current)
    setDataset(d); write(KEY, d.id); resetFilters()
    return d
  }, [resetFilters])

  const prepare = useCallback(async (mapping: Mapping, options: { drop_duplicates: boolean; separate_returns: boolean; cancellation_prefix?: string | null }) => {
    if (!dataset) return
    const d = await api.prepare(dataset.id, mapping, options)
    if (cached.current?.id === dataset.id) { cached.current = { ...cached.current, mapping, options }; saveUpload(cached.current) }
    setDataset(d)
  }, [dataset])

  const reset = useCallback(async () => {
    if (dataset) { try { await api.reset(dataset.id) } catch { /* already gone */ } }
    cached.current = null; clearUpload()
    resetFilters(); write(KEY, null)
    await openSample()
  }, [dataset, openSample, resetFilters])

  const cur = useMemo(() => ({ GBP: '£', USD: '$', EUR: '€', PKR: 'Rs ' } as Record<string, string>)[dataset?.meta?.currency || ''] || '', [dataset])

  const value = { dataset, loading, error, filters, setFilters, resetFilters, target, setTarget, openSample, upload, prepare, reset, cur }
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useWorkspace() {
  const c = useContext(Ctx)
  if (!c) throw new Error('useWorkspace must be used inside WorkspaceProvider')
  return c
}
