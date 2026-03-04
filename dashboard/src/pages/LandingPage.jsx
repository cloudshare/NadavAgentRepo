import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router'
import { startRun, getRun, listRuns } from '../api'
import { usePolling } from '../hooks/usePolling'

export default function LandingPage() {
  const navigate = useNavigate()
  const [testFolder, setTestFolder] = useState('')
  const [logFolder, setLogFolder] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [runId, setRunId] = useState(null)
  const [submitError, setSubmitError] = useState(null)
  const [history, setHistory] = useState([])

  // Load run history on mount
  useEffect(() => {
    listRuns()
      .then(setHistory)
      .catch((err) => console.error('Failed to load run history:', err))
  }, [])

  // Polling: only active when runId is set
  const fetchFn = useCallback(() => getRun(runId), [runId])
  const { data: pollData, error: pollError, done: pollDone } = usePolling(
    runId ? fetchFn : null,
    2000
  )

  // Navigate to results when done
  useEffect(() => {
    if (pollDone && pollData?.status === 'completed') {
      navigate(`/runs/${runId}`)
    }
  }, [pollDone, pollData, runId, navigate])

  async function handleSubmit(e) {
    e.preventDefault()
    if (!testFolder || !logFolder) return
    setSubmitting(true)
    setSubmitError(null)
    try {
      const { run_id } = await startRun(testFolder, logFolder)
      setRunId(run_id)
    } catch (err) {
      setSubmitError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div style={{ maxWidth: '900px', margin: '40px auto', padding: '0 20px', fontFamily: 'sans-serif' }}>
      <h1 style={{ marginBottom: '8px' }}>CloudShare E2E Intelligence Analyzer</h1>
      <p style={{ color: '#6b7280', marginBottom: '32px' }}>
        Submit a folder of test logs for AI-powered failure classification and insight generation.
      </p>

      {!runId ? (
        <form onSubmit={handleSubmit} style={{ background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '24px', marginBottom: '40px' }}>
          <h2 style={{ marginTop: 0, marginBottom: '20px' }}>New Analysis Run</h2>
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', marginBottom: '6px', fontWeight: 500 }}>
              Test code folder (path to .spec.ts files)
            </label>
            <input
              type="text"
              value={testFolder}
              onChange={(e) => setTestFolder(e.target.value)}
              placeholder="/path/to/tests"
              style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '14px', boxSizing: 'border-box' }}
              required
            />
          </div>
          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', marginBottom: '6px', fontWeight: 500 }}>
              Log folder (path to Playwright JSON or stdout logs)
            </label>
            <input
              type="text"
              value={logFolder}
              onChange={(e) => setLogFolder(e.target.value)}
              placeholder="/path/to/logs"
              style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '14px', boxSizing: 'border-box' }}
              required
            />
          </div>
          {submitError && (
            <p style={{ color: '#dc2626', marginBottom: '12px' }}>{submitError}</p>
          )}
          <button
            type="submit"
            disabled={submitting}
            style={{ background: '#2563eb', color: '#fff', border: 'none', padding: '10px 24px', borderRadius: '4px', fontSize: '14px', cursor: 'pointer', opacity: submitting ? 0.6 : 1 }}
          >
            {submitting ? 'Submitting...' : 'Start Analysis'}
          </button>
        </form>
      ) : (
        <div style={{ background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '24px', marginBottom: '40px' }}>
          <h2 style={{ marginTop: 0 }}>Analysis Running</h2>
          <p>Run ID: <code style={{ background: '#e5e7eb', padding: '2px 6px', borderRadius: '3px' }}>{runId}</code></p>
          {pollError ? (
            <p style={{ color: '#dc2626' }}>Polling error: {pollError}</p>
          ) : pollData?.status === 'failed' ? (
            <p style={{ color: '#dc2626' }}>Analysis failed. Check server logs.</p>
          ) : (
            <p style={{ color: '#2563eb' }}>Analyzing... polling every 2 seconds.</p>
          )}
        </div>
      )}

      <h2>Run History</h2>
      {history.length === 0 ? (
        <p style={{ color: '#9ca3af' }}>No previous runs found.</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: '#f3f4f6' }}>
              <th style={{ textAlign: 'left', padding: '10px 12px', borderBottom: '1px solid #e5e7eb' }}>Run ID</th>
              <th style={{ textAlign: 'left', padding: '10px 12px', borderBottom: '1px solid #e5e7eb' }}>Created</th>
              <th style={{ textAlign: 'right', padding: '10px 12px', borderBottom: '1px solid #e5e7eb' }}>Total</th>
              <th style={{ textAlign: 'right', padding: '10px 12px', borderBottom: '1px solid #e5e7eb' }}>Failed</th>
              <th style={{ textAlign: 'right', padding: '10px 12px', borderBottom: '1px solid #e5e7eb' }}>Cost (USD)</th>
            </tr>
          </thead>
          <tbody>
            {history.map((run) => (
              <tr
                key={run.run_id}
                onClick={() => navigate(`/runs/${run.run_id}`)}
                style={{ cursor: 'pointer', borderBottom: '1px solid #f3f4f6' }}
                onMouseEnter={(e) => e.currentTarget.style.background = '#f9fafb'}
                onMouseLeave={(e) => e.currentTarget.style.background = ''}
              >
                <td style={{ padding: '10px 12px', fontFamily: 'monospace', fontSize: '12px' }}>
                  {run.run_id.slice(0, 8)}...
                </td>
                <td style={{ padding: '10px 12px', fontSize: '13px' }}>
                  {new Date(run.created_at).toLocaleString()}
                </td>
                <td style={{ textAlign: 'right', padding: '10px 12px' }}>{run.total_tests}</td>
                <td style={{ textAlign: 'right', padding: '10px 12px', color: run.failed_tests > 0 ? '#dc2626' : '#16a34a' }}>
                  {run.failed_tests}
                </td>
                <td style={{ textAlign: 'right', padding: '10px 12px' }}>
                  ${run.estimated_cost_usd?.toFixed(4) ?? '0.0000'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
