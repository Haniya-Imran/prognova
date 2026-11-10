/* eslint-disable @typescript-eslint/no-explicit-any */
import Plotly from 'plotly.js-dist-min'
import createPlotlyComponent from 'react-plotly.js/factory'
import { useEffect, useMemo, useState } from 'react'

const Plot = createPlotlyComponent(Plotly as any)

function cssVar(name: string, fallback: string) {
  if (typeof window === 'undefined') return fallback
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
}

/** Same colour with transparency, for fills and bands (Plotly cannot read CSS variables). */
export function alpha(hex: string, a: number) {
  const h = hex.replace('#', '')
  const n = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16)
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`
}

export function palette() {
  return [1, 2, 3, 4, 5, 6].map((i) => cssVar(`--c${i}`, '#2ee6c8'))
}

function useTheme() {
  const [, force] = useState(0)
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const on = () => force((x) => x + 1)
    mq.addEventListener?.('change', on)
    return () => mq.removeEventListener?.('change', on)
  }, [])
  return {
    ink: cssVar('--ink', '#2a1622'),
    muted: cssVar('--muted', '#6b5462'),
    line: cssVar('--line', '#eadde3'),
    font: cssVar('--font-ui', 'Manrope, system-ui, sans-serif'),
  }
}

export function Chart({ data, layout = {}, height = 340, ariaLabel, onClick, config = {} }: {
  data: any[]; layout?: any; height?: number; ariaLabel: string; onClick?: (e: any) => void; config?: any
}) {
  const t = useTheme()
  const merged = useMemo(() => ({
    autosize: true,
    height,
    margin: { l: 56, r: 16, t: 12, b: 44 },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { family: t.font, color: t.ink, size: 12 },
    hoverlabel: { font: { family: t.font, color: '#eaf0ff' }, bgcolor: '#2f4069', bordercolor: 'rgba(46,230,200,.45)' },
    legend: { orientation: 'h', y: -0.18, x: 0, font: { color: t.muted } },
    colorway: palette(),
    ...layout,
    xaxis: { gridcolor: t.line, linecolor: t.line, zeroline: false, tickfont: { color: t.muted }, automargin: true, ...(layout.xaxis || {}) },
    yaxis: { gridcolor: t.line, linecolor: t.line, zeroline: false, tickfont: { color: t.muted }, automargin: true, ...(layout.yaxis || {}) },
  }), [layout, height, t])
  return (
    <div className="chart" role="img" aria-label={ariaLabel}>
      <Plot data={data} layout={merged} useResizeHandler style={{ width: '100%', height }} onClick={onClick}
        config={{ displaylogo: false, responsive: true, modeBarButtonsToRemove: ['lasso2d', 'select2d'],
          toImageButtonOptions: { format: 'png', filename: ariaLabel.replace(/\W+/g, '_').toLowerCase() }, ...config }} />
    </div>
  )
}
