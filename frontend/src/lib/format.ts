export function money(v: number | null | undefined, cur = '', digits?: number): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  const a = Math.abs(v)
  const sign = v < 0 ? '-' : ''
  if (digits === undefined) {
    if (a >= 1e6) return `${sign}${cur}${(a / 1e6).toFixed(2)}M`
    if (a >= 1e4) return `${sign}${cur}${(a / 1e3).toFixed(1)}K`
    return `${sign}${cur}${a.toLocaleString('en-GB', { maximumFractionDigits: 2 })}`
  }
  return `${sign}${cur}${a.toLocaleString('en-GB', { minimumFractionDigits: digits, maximumFractionDigits: digits })}`
}

export function num(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return v.toLocaleString('en-GB', { maximumFractionDigits: digits, minimumFractionDigits: 0 })
}

export function compact(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  const a = Math.abs(v)
  if (a >= 1e6) return `${(v / 1e6).toFixed(2)}M`
  if (a >= 1e4) return `${(v / 1e3).toFixed(1)}K`
  return num(v, 1)
}

export function pct(v: number | null | undefined, digits = 1, signed = true): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return `${signed && v > 0 ? '+' : ''}${v.toFixed(digits)}%`
}

export function currencySymbol(meta: { currency?: string } | undefined): string {
  return ({ GBP: '£', USD: '$', EUR: '€', PKR: 'Rs ' } as Record<string, string>)[meta?.currency || ''] || ''
}

export function monthLabel(ym: string): string {
  const [y, m] = ym.split('-').map(Number)
  return new Date(y, m - 1, 1).toLocaleString('en-GB', { month: 'short', year: 'numeric' })
}
