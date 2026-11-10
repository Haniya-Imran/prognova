import { lazy, Suspense, useEffect, useRef, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { BRAND } from '../brand'
import { Logo } from '../components/Logo'
import { api } from '../lib/api'
import './landing.css'

const Hero3D = lazy(() => import('./Hero3D'))

function Tilt({ children, className = '' }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  return (
    <div ref={ref} className={`tilt ${className}`}
      onMouseMove={(e) => {
        const el = ref.current; if (!el) return
        const r = el.getBoundingClientRect()
        const x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5
        el.style.transform = `perspective(900px) rotateY(${x * 10}deg) rotateX(${-y * 10}deg) translateZ(0)`
        el.style.setProperty('--mx', `${(x + 0.5) * 100}%`); el.style.setProperty('--my', `${(y + 0.5) * 100}%`)
      }}
      onMouseLeave={() => { if (ref.current) ref.current.style.transform = '' }}>
      {children}
    </div>
  )
}

const FEATURES = [
  { k: '01', t: 'Honest data preparation', d: 'Over a million real transactions. Duplicates, returns, fees and bad rows are handled — and every rule is logged with the rows it touched.', icon: '◇' },
  { k: '02', t: 'EDA Studio', d: 'Trends, seasonality index, weekday and hour patterns, distributions, correlations, best and weakest products and markets.', icon: '◎' },
  { k: '03', t: 'Interactive Plotly dashboard', d: 'Filter by dates, products and regions. KPIs and every chart recalculate from the transactions. Click a bar to drill in.', icon: '▦' },
  { k: '04', t: 'Backtested 3-month forecast', d: 'Eight models compete on months they never saw. The most accurate one forecasts the next three calendar months with an honest range.', icon: '✦' },
]

const FLOW = ['Data Hub', 'Data Quality', 'EDA Studio', 'Dashboard', 'Forecasting Lab', 'Insights & Reports']

export default function Landing() {
  const [webgl, setWebgl] = useState(true)
  useEffect(() => {
    try { const c = document.createElement('canvas'); setWebgl(!!(c.getContext('webgl2') || c.getContext('webgl'))) } catch { setWebgl(false) }
    api.health().catch(() => undefined) // warm the API while the visitor reads
  }, [])
  return (
    <div className="landing">
      <section className="hero" aria-labelledby="hero-title">
        <div className="hero-scene" aria-hidden>
          {webgl ? <Suspense fallback={<div className="hero-fallback" />}><Hero3D /></Suspense> : <div className="hero-fallback" />}
        </div>
        <div className="hero-vignette" aria-hidden />

        <header className="l-nav">
          <Link to="/" className="l-brand"><Logo size={36} /><b>{BRAND.name}</b></Link>
          <nav aria-label="Main">
            <a href="#features">Features</a>
            <a href="#how">How it works</a>
            <Link className="btn btn-primary" to="/app">Open workspace</Link>
          </nav>
        </header>

        <div className="hero-body">
          <div className="hero-copy">
            <span className="pill"><span className="dot" /> Sales intelligence · EDA · Forecasting</span>
            <h1 id="hero-title">See what sold.<br /><span className="grad">Know what's next.</span></h1>
            <p>Prognova turns raw sales transactions into a clear story — and a three-month forecast that was tested on months it had never seen, shown with an honest range.</p>
            <div className="row">
              <Link className="btn btn-primary btn-lg" to="/app/dashboard">Open the dashboard</Link>
              <Link className="btn btn-lg" to="/app/forecast">See the forecast →</Link>
            </div>
            <p className="hero-note">No sign-up. Opens with 1M+ real retail transactions; bring your own CSV anytime.</p>
          </div>
          <div className="hero-cards" aria-label="Demo data results">
            <div className="glass gc-1"><span>Next 3 months (demo data)</span><b>£2.24M</b><small>80% range £1.81M – £2.66M</small></div>
            <div className="glass gc-2"><span>Backtest error</span><b>10.6%</b><small>WAPE over 7 rolling windows</small></div>
            <div className="glass gc-3"><span>Teal towers</span><b>24 real months</b><small>Amber = forecast · ghost = upper range</small></div>
          </div>
        </div>
      </section>

      <section id="features" className="l-section">
        <span className="eyebrow">What's inside</span>
        <h2>One workspace, from raw rows to decisions</h2>
        <div className="l-grid">
          {FEATURES.map((f) => (
            <Tilt key={f.k} className="l-card">
              <div className="l-icon" aria-hidden>{f.icon}</div>
              <span className="k">{f.k}</span>
              <h3>{f.t}</h3>
              <p>{f.d}</p>
            </Tilt>
          ))}
        </div>
      </section>

      <section id="how" className="l-section">
        <span className="eyebrow">How it works</span>
        <h2>Six steps, one clean dataset</h2>
        <ol className="stairs">
          {FLOW.map((s, i) => <li key={s} style={{ ['--i' as string]: i }}><span>{String(i + 1).padStart(2, '0')}</span>{s}</li>)}
        </ol>
        <div className="cta glass">
          <div>
            <h3>Ready to look ahead?</h3>
            <p>Open the workspace — the real demo dataset is already loaded.</p>
          </div>
          <Link className="btn btn-primary btn-lg" to="/app">Start exploring</Link>
        </div>
      </section>

      <footer className="l-foot">
        <span className="l-brand small-brand"><Logo size={22} /><b>{BRAND.name}</b> · Built by {BRAND.author}</span>
        <span>Demo data: UCI Online Retail II (Chen, 2012), CC BY 4.0. Forecasts are estimates, not guarantees. Revenue is not profit.</span>
      </footer>
    </div>
  )
}
