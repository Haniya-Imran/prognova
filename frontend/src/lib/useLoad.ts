import { useCallback, useEffect, useRef, useState } from 'react'

/** Load data with loading / error / retry states. Ignores stale responses. */
export function useLoad<T>(fn: (() => Promise<T>) | null, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const seq = useRef(0)
  const run = useCallback(() => {
    if (!fn) return
    const n = ++seq.current
    setLoading(true); setError(null)
    fn().then((d) => { if (n === seq.current) setData(d) })
      .catch((e: Error) => { if (n === seq.current) setError(e.message) })
      .finally(() => { if (n === seq.current) setLoading(false) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  useEffect(() => { run() }, [run])
  return { data, error, loading, retry: run }
}
