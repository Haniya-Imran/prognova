import { lazy, Suspense } from 'react'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import Landing from './landing/Landing'
import { Loading } from './components/ui'

// The workspace (and Plotly) loads only when someone opens it, so the landing page stays fast.
const WorkspaceApp = lazy(() => import('./workspace/WorkspaceApp'))

function NotFound() {
  return (
    <div style={{ padding: 40 }}>
      <h1>Page not found</h1>
      <p style={{ margin: '12px 0' }}>That address does not exist.</p>
      <Link className="btn btn-primary" to="/">Go home</Link>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/app/*" element={<Suspense fallback={<div style={{ padding: 32 }}><Loading label="Loading workspace…" /></div>}><WorkspaceApp /></Suspense>} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  )
}
