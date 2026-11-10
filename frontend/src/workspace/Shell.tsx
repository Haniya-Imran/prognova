import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { BRAND } from '../brand'
import { Logo } from '../components/Logo'
import { useWorkspace } from '../state/Workspace'
import { ErrorState, Loading } from '../components/ui'
import { num } from '../lib/format'

export const NAV = [
  { to: '/app', label: 'Overview', step: '◎', end: true },
  { to: '/app/data', label: 'Data Hub', step: 'A' },
  { to: '/app/quality', label: 'Data Quality', step: 'B' },
  { to: '/app/eda', label: 'EDA Studio', step: 'C' },
  { to: '/app/dashboard', label: 'Sales Dashboard', step: 'D' },
  { to: '/app/forecast', label: 'Forecasting Lab', step: 'E' },
  { to: '/app/insights', label: 'Business Insights', step: 'F' },
  { to: '/app/reports', label: 'Reports', step: 'G' },
]

export function Shell() {
  const { dataset, loading, error, openSample } = useWorkspace()
  const [open, setOpen] = useState(false)
  const loc = useLocation()
  useEffect(() => { setOpen(false); window.scrollTo({ top: 0 }) }, [loc.pathname])

  const side = (
    <aside className={`side ${open ? 'open' : ''}`} aria-label="Workspace navigation">
      <Link to="/" className="brand"><Logo size={36} /><span><b>{BRAND.name}</b><small>Sales workspace</small></span></Link>
      <nav className="nav">
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end}><span className="step">{n.step}</span>{n.label}</NavLink>
        ))}
      </nav>
      {dataset && (
        <div className="dataset-chip">
          <b>{dataset.name}</b>
          {dataset.status === 'ready'
            ? <>{num(dataset.rows)} clean sales lines<br />{dataset.date_min} → {dataset.date_max}</>
            : <>Waiting for column mapping</>}
        </div>
      )}
      <div className="side-foot">
        No sign-in needed. Uploaded files stay in server memory for this session only.<br />
        Built by {BRAND.author}
      </div>
    </aside>
  )

  return (
    <div className="shell">
      <div className="topbar">
        <Link to="/" className="brand"><Logo size={28} /><span><b>{BRAND.name}</b></span></Link>
        <button className="btn btn-sm" onClick={() => setOpen(true)} aria-expanded={open} aria-label="Open navigation">Menu</button>
      </div>
      {open && <div className="scrim" onClick={() => setOpen(false)} />}
      {side}
      <main className="main" id="main">
        {loading && !dataset ? <Loading label="Opening the workspace… (the free server can take ~1 minute to wake up)" rows={4} />
          : error && !dataset ? <ErrorState message={error} onRetry={openSample} />
            : <Outlet />}
      </main>
    </div>
  )
}
