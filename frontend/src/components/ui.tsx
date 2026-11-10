import { useId, useState, type ReactNode } from 'react'

export function Card({ title, sub, info, actions, children, className = '', id }: {
  title?: ReactNode; sub?: ReactNode; info?: string; actions?: ReactNode; children: ReactNode; className?: string; id?: string
}) {
  return (
    <section className={`card ${className}`} id={id}>
      {(title || actions) && (
        <header className="card-head">
          <div>
            {title && <h3>{title}{info && <Info text={info} />}</h3>}
            {sub && <p className="sub">{sub}</p>}
          </div>
          {actions && <div className="card-actions">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  )
}

export function PageHead({ step, title, lead, actions }: { step?: string; title: string; lead?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="page-head">
      <div>
        {step && <span className="eyebrow">{step}</span>}
        <h1>{title}</h1>
        {lead && <p className="lead">{lead}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  )
}

export function Info({ text }: { text: string }) {
  const id = useId()
  const [open, setOpen] = useState(false)
  return (
    <span className="info" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button type="button" className="info-btn" aria-label="What does this mean?" aria-describedby={open ? id : undefined}
        onFocus={() => setOpen(true)} onBlur={() => setOpen(false)} onClick={() => setOpen((o) => !o)}>i</button>
      {open && <span role="tooltip" id={id} className="info-tip">{text}</span>}
    </span>
  )
}

export function Kpi({ label, value, delta, deltaLabel, info, tone }: {
  label: string; value: ReactNode; delta?: number | null; deltaLabel?: string; info?: string; tone?: 'brand' | 'plain'
}) {
  const dir = delta === null || delta === undefined ? 'none' : delta > 0.05 ? 'up' : delta < -0.05 ? 'down' : 'flat'
  return (
    <div className={`kpi ${tone === 'brand' ? 'kpi-brand' : ''}`}>
      <span className="kpi-label">{label}{info && <Info text={info} />}</span>
      <strong className="kpi-value">{value}</strong>
      {deltaLabel !== undefined && (
        <span className={`kpi-delta ${dir}`}>
          {dir === 'none' ? deltaLabel : `${dir === 'up' ? '▲' : dir === 'down' ? '▼' : '■'} ${deltaLabel}`}
        </span>
      )}
    </div>
  )
}

export function Loading({ label = 'Loading…', rows = 3 }: { label?: string; rows?: number }) {
  return (
    <div className="loading" role="status" aria-live="polite">
      <span className="spinner" aria-hidden />
      <span>{label}</span>
      <div className="skeletons" aria-hidden>{Array.from({ length: rows }).map((_, i) => <div key={i} className="skeleton" />)}</div>
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="state state-error" role="alert">
      <strong>Something went wrong</strong>
      <p>{message}</p>
      {onRetry && <button className="btn" onClick={onRetry}>Try again</button>}
    </div>
  )
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="state state-empty">
      <strong>{title}</strong>
      {children && <p>{children}</p>}
    </div>
  )
}

export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'good' | 'warn' | 'bad' | 'brand' }) {
  return <span className={`badge badge-${tone}`}>{children}</span>
}

export function Segmented<T extends string>({ value, onChange, options, label }: {
  value: T; onChange: (v: T) => void; options: { value: T; label: string; disabled?: boolean }[]; label: string
}) {
  return (
    <div className="segmented" role="radiogroup" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} type="button" role="radio" aria-checked={value === o.value} disabled={o.disabled}
          className={value === o.value ? 'on' : ''} onClick={() => onChange(o.value)}>{o.label}</button>
      ))}
    </div>
  )
}

export function Note({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'warn' }) {
  return <div className={`note note-${tone}`}>{children}</div>
}
