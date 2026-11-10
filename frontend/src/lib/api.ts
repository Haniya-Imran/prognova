// Centralized API client. Every screen talks to the FastAPI backend through here.
/* eslint-disable @typescript-eslint/no-explicit-any */

// Same origin by default: on Vercel the API is served at /api next to the site.
// For local dev, Vite proxies /api to the FastAPI server (see vite.config.ts).
export const API_URL: string = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

// Serverless instances can restart and forget an uploaded file. When that happens the
// workspace registers a function that re-sends the file and mapping, then we retry once.
let recover: ((datasetId: string) => Promise<boolean>) | null = null
export function setRecovery(fn: ((datasetId: string) => Promise<boolean>) | null) { recover = fn }

export class ApiError extends Error {
  code: string
  status: number
  details: unknown
  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

async function request<T>(path: string, init: RequestInit = {}, timeoutMs = 90000, retried = false): Promise<T> {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeoutMs)
  let res: Response
  try {
    res = await fetch(API_URL + path, { ...init, signal: ctrl.signal })
  } catch (e: any) {
    clearTimeout(timer)
    if (e?.name === 'AbortError') throw new ApiError(0, 'timeout', 'The server took too long to answer. It may be waking up — try again in a moment.')
    throw new ApiError(0, 'network', 'Cannot reach the analysis server. Check your connection, or wait ~1 minute if it is waking up.')
  }
  clearTimeout(timer)
  const text = await res.text()
  let body: any = null
  try { body = text ? JSON.parse(text) : null } catch { body = null }
  if (!res.ok) {
    const err = body?.error
    if (!retried && err?.code === 'dataset_not_found' && recover) {
      const id = path.split('/')[3]
      if (id && (await recover(id))) return request<T>(path, init, timeoutMs, true)
    }
    throw new ApiError(res.status, err?.code || 'http_error', err?.message || `Request failed (${res.status})`, err?.details)
  }
  return body as T
}

const json = (body: unknown): RequestInit => ({
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
})

export type Mapping = Partial<Record<'date' | 'revenue' | 'quantity' | 'unit_price' | 'order_id' | 'product' | 'category' | 'region' | 'store' | 'customer', string | null>>

export interface Filters {
  start?: string | null
  end?: string | null
  product: string[]
  category: string[]
  region: string[]
  store: string[]
}
export const emptyFilters = (): Filters => ({ start: null, end: null, product: [], category: [], region: [], store: [] })

export type Target = 'net_revenue' | 'gross_revenue' | 'units'

export interface DatasetSummary {
  id: string
  name: string
  source: 'sample' | 'upload'
  status: 'ready' | 'needs_mapping'
  meta: any
  mapping: Mapping | null
  raw_columns: string[]
  read_info: any
  detection: any
  rows?: number
  return_rows?: number
  date_min?: string
  date_max?: string
  available?: Record<string, boolean>
  dimensions?: Record<string, boolean>
  has_time_of_day?: boolean
  steps?: { step: string; rows_affected: number; detail: string }[]
  quality?: any
  preview?: Record<string, string>[]
  frequency?: any
}

export interface Job { job_id: string; status: 'queued' | 'running' | 'done' | 'failed'; stage: string; result: any; error: any; elapsed_seconds: number }

export const api = {
  health: () => request<{ status: string; sample_loaded: boolean }>('/health', {}, 70000),
  sample: () => request<DatasetSummary>('/api/datasets/sample', {}, 120000),
  dataset: (id: string) => request<DatasetSummary>(`/api/datasets/${id}`),
  upload: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return request<DatasetSummary>('/api/datasets/upload', { method: 'POST', body: fd }, 180000)
  },
  qualityCheck: (id: string, mapping: Mapping) => request<any>(`/api/datasets/${id}/quality-check`, json({ mapping })),
  prepare: (id: string, mapping: Mapping, options: { drop_duplicates: boolean; separate_returns: boolean; cancellation_prefix?: string | null }) =>
    request<DatasetSummary>(`/api/datasets/${id}/prepare`, json({ mapping, options }), 180000),
  rows: (id: string, page: number, size: number, table: 'sales' | 'returns') =>
    request<any>(`/api/datasets/${id}/rows?page=${page}&size=${size}&table=${table}`),
  reset: (id: string) => request<any>(`/api/datasets/${id}`, { method: 'DELETE' }),
  eda: (id: string) => request<any>(`/api/analytics/${id}/eda`, {}, 120000),
  dashboard: (id: string, filters: Filters, grain?: string | null) => request<any>(`/api/analytics/${id}/dashboard`, json({ filters, grain: grain || null })),
  dimension: (id: string, dim: string, q = '', limit = 50) =>
    request<{ values: { value: string; revenue: number }[] }>(`/api/analytics/${id}/dimensions/${dim}?q=${encodeURIComponent(q)}&limit=${limit}`),
  runForecast: (id: string, target: Target, filters: Filters) => request<Job>(`/api/forecast/${id}/run`, json({ target, filters })),
  job: (jobId: string) => request<Job>(`/api/forecast/jobs/${jobId}`),
  insights: (id: string, target: Target) => request<any>(`/api/insights/${id}?target=${target}`, {}, 150000),
}

export function reportUrl(id: string, kind: string, ext: 'html' | 'csv', opts: { target?: Target; filters?: Filters } = {}) {
  const p = new URLSearchParams()
  if (opts.target) p.set('target', opts.target)
  if (opts.filters) p.set('filters', JSON.stringify(opts.filters))
  return `${API_URL}/api/reports/${id}/${kind}.${ext}?${p.toString()}`
}

/** Download through fetch so errors show in the app instead of a blank tab. */
export async function download(url: string, filename: string, retried = false): Promise<void> {
  const res = await fetch(url)
  if (res.status === 404 && !retried && recover) {
    const id = new URL(url, window.location.href).pathname.split('/')[3]
    let code = ''
    try { code = (await res.clone().json()).error.code } catch { /* not JSON */ }
    if (code === 'dataset_not_found' && id && (await recover(id))) return download(url, filename, true)
  }
  if (!res.ok) {
    let msg = `Download failed (${res.status})`
    try { msg = (await res.json()).error.message } catch { /* not JSON */ }
    throw new ApiError(res.status, 'download_failed', msg)
  }
  const blob = await res.blob()
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(a.href), 2000)
}

/** Poll a forecast job until it finishes. */
export async function waitForJob(job: Job, onUpdate: (j: Job) => void, signal?: { cancelled: boolean }): Promise<Job> {
  let j = job
  onUpdate(j)
  while (j.status === 'queued' || j.status === 'running') {
    await new Promise((r) => setTimeout(r, 700))
    if (signal?.cancelled) return j
    j = await api.job(j.job_id)
    onUpdate(j)
  }
  return j
}
