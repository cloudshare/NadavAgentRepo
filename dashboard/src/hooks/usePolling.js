import { useState, useEffect, useRef } from 'react'

/**
 * usePolling — calls fetchFn every intervalMs until status is terminal.
 * Uses useRef to avoid stale closure. Always cleans up interval on unmount.
 *
 * @param {Function|null} fetchFn - async function returning { status, ... }, or null to disable
 * @param {number} intervalMs - polling interval in ms (default 2000)
 * @returns {{ data, error, done }}
 */
export function usePolling(fetchFn, intervalMs = 2000) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(false)
  const fetchRef = useRef(fetchFn)

  useEffect(() => {
    if (fetchFn) fetchRef.current = fetchFn
  }, [fetchFn])

  useEffect(() => {
    if (done || !fetchFn) return
    const id = setInterval(async () => {
      try {
        const result = await fetchRef.current()
        setData(result)
        if (result.status === 'completed' || result.status === 'failed') {
          setDone(true)
          clearInterval(id)
        }
      } catch (err) {
        setError(err.message)
      }
    }, intervalMs)
    return () => clearInterval(id)  // always clean up
  }, [done, intervalMs, fetchFn])

  return { data, error, done }
}
