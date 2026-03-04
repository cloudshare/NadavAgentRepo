import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router'
import { getRun } from '../api'
import { HeatmapGrid } from '../components/HeatmapGrid'
import { RetryImpactChart } from '../components/RetryImpactChart'

export default function TestDrillDown() {
  const { runId, testIndex } = useParams()
  const navigate = useNavigate()
  const currentIndex = parseInt(testIndex ?? '0', 10)

  const [runData, setRunData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    getRun(runId)
      .then(setRunData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [runId])

  if (loading) {
    return <div style={{ padding: '40px', fontFamily: 'sans-serif' }}>Loading...</div>
  }

  if (error) {
    return (
      <div style={{ padding: '40px', fontFamily: 'sans-serif', color: '#dc2626' }}>
        Error: {error}
      </div>
    )
  }

  if (!runData) return null

  const tests = runData.report?.tests ?? []
  const test = tests[currentIndex]
  const totalTests = tests.length

  const endpointHeatmap = runData.report?.endpoint_heatmap ?? []
  const flakinessData = runData.report?.flakiness_index ?? []

  function goToTest(index) {
    if (index >= 0 && index < totalTests) {
      navigate(`/runs/${runId}/tests/${index}`)
    }
  }

  return (
    <div style={{ maxWidth: '960px', margin: '40px auto', padding: '0 20px', fontFamily: 'sans-serif' }}>
      {/* Navigation */}
      <div style={{ display: 'flex', gap: '16px', marginBottom: '24px', alignItems: 'center' }}>
        <Link to={`/runs/${runId}`} style={{ color: '#2563eb', fontSize: '14px' }}>
          &larr; Back to Overview
        </Link>
        <span style={{ color: '#9ca3af', fontSize: '14px' }}>
          Test {currentIndex + 1} of {totalTests}
        </span>
        <div style={{ display: 'flex', gap: '8px', marginLeft: 'auto' }}>
          <button
            onClick={() => goToTest(currentIndex - 1)}
            disabled={currentIndex <= 0}
            style={{ padding: '6px 14px', border: '1px solid #d1d5db', borderRadius: '4px', cursor: currentIndex <= 0 ? 'not-allowed' : 'pointer', opacity: currentIndex <= 0 ? 0.4 : 1 }}
          >
            &larr; Prev
          </button>
          <button
            onClick={() => goToTest(currentIndex + 1)}
            disabled={currentIndex >= totalTests - 1}
            style={{ padding: '6px 14px', border: '1px solid #d1d5db', borderRadius: '4px', cursor: currentIndex >= totalTests - 1 ? 'not-allowed' : 'pointer', opacity: currentIndex >= totalTests - 1 ? 0.4 : 1 }}
          >
            Next &rarr;
          </button>
        </div>
      </div>

      {!test ? (
        <p style={{ color: '#dc2626' }}>Test index {currentIndex} not found in this run (total: {totalTests}).</p>
      ) : (
        <>
          {/* Test identity */}
          <h1 style={{ fontSize: '20px', marginBottom: '4px', wordBreak: 'break-word' }}>
            {test.test_title ?? test.full_title ?? 'Unnamed Test'}
          </h1>
          {test.full_title && test.full_title !== test.test_title && (
            <p style={{ color: '#6b7280', fontSize: '13px', fontFamily: 'monospace', marginBottom: '24px' }}>
              {test.full_title}
            </p>
          )}

          {/* Classification summary */}
          <section style={{ background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '20px', marginBottom: '32px' }}>
            <h2 style={{ marginTop: 0, marginBottom: '16px' }}>Classification</h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
              <Field label="Category" value={test.category ?? 'unknown'} mono />
              <Field
                label="Root Cause Probability"
                value={test.probability != null ? `${(test.probability * 100).toFixed(0)}%` : 'N/A'}
              />
              <Field label="Method" value={test.method ?? 'unknown'} mono />
              <Field label="Status" value={test.status ?? 'unknown'} />
              <Field label="Retry Count" value={test.retry_count ?? 0} />
            </div>
          </section>

          {/* Fix recommendation */}
          {test.fix_recommendation && (
            <section style={{ marginBottom: '32px' }}>
              <h2 style={{ marginBottom: '12px' }}>Fix Recommendation</h2>
              <p style={{ background: '#ecfdf5', border: '1px solid #6ee7b7', borderRadius: '6px', padding: '12px 16px', margin: 0, lineHeight: 1.6 }}>
                {test.fix_recommendation}
              </p>
            </section>
          )}

          {/* Root cause summary */}
          {test.summary_paragraph && (
            <section style={{ marginBottom: '32px' }}>
              <h2 style={{ marginBottom: '12px' }}>Root Cause Summary</h2>
              <p style={{ lineHeight: 1.7, margin: 0 }}>{test.summary_paragraph}</p>
            </section>
          )}

          {/* First real error */}
          {test.first_real_error && (
            <section style={{ marginBottom: '32px' }}>
              <h2 style={{ marginBottom: '12px' }}>First Real Error</h2>
              <pre style={{
                background: '#fef2f2',
                border: '1px solid #fecaca',
                borderRadius: '6px',
                padding: '12px 16px',
                fontSize: '13px',
                fontFamily: 'monospace',
                overflowX: 'auto',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                margin: 0,
              }}>
                {test.first_real_error}
              </pre>
            </section>
          )}

          {/* Stack trace */}
          {test.stack_trace && (
            <section style={{ marginBottom: '32px' }}>
              <h2 style={{ marginBottom: '12px' }}>Stack Trace</h2>
              <pre style={{
                background: '#f9fafb',
                border: '1px solid #e5e7eb',
                borderRadius: '6px',
                padding: '12px 16px',
                fontSize: '12px',
                fontFamily: 'monospace',
                overflowX: 'auto',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                margin: 0,
                maxHeight: '300px',
                overflowY: 'auto',
              }}>
                {test.stack_trace}
              </pre>
            </section>
          )}

          {/* DASH-07: LLM Reasoning Chain — ALWAYS VISIBLE, never in a collapsible */}
          <section style={{ marginBottom: '32px' }}>
            <h2 style={{ marginBottom: '4px' }}>LLM Reasoning Chain</h2>
            <p style={{ color: '#6b7280', fontSize: '13px', marginBottom: '12px' }}>
              Always visible so you can detect hallucinations and verify the reasoning is grounded in real log evidence.
            </p>
            {!test.reasoning_chain || test.reasoning_chain.length === 0 ? (
              <p style={{ color: '#9ca3af' }}>
                {test.method === 'rule_engine'
                  ? 'Classification was determined by rule engine (no LLM reasoning for this test).'
                  : 'No reasoning chain recorded.'}
              </p>
            ) : (
              <ol style={{
                margin: 0,
                paddingLeft: '24px',
                background: '#f0f9ff',
                border: '1px solid #bae6fd',
                borderRadius: '6px',
                padding: '16px 16px 16px 40px',
              }}>
                {test.reasoning_chain.map((step, i) => (
                  <li
                    key={i}
                    style={{
                      marginBottom: i < test.reasoning_chain.length - 1 ? '10px' : 0,
                      lineHeight: 1.6,
                      fontSize: '14px',
                    }}
                  >
                    {step}
                  </li>
                ))}
              </ol>
            )}
          </section>

          {/* Correlated API endpoints */}
          {test.correlated_endpoints && test.correlated_endpoints.length > 0 && (
            <section style={{ marginBottom: '32px' }}>
              <h2 style={{ marginBottom: '12px' }}>Correlated API Endpoints</h2>
              <ul style={{ margin: 0, paddingLeft: '20px' }}>
                {test.correlated_endpoints.map((ep, i) => (
                  <li key={i} style={{ fontFamily: 'monospace', fontSize: '13px', marginBottom: '4px' }}>
                    {ep}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}

      {/* Run-level heatmaps and retry chart — always shown regardless of selected test */}
      <hr style={{ margin: '40px 0', borderColor: '#e5e7eb' }} />

      <h2 style={{ marginBottom: '24px' }}>Run-Level Analysis</h2>

      <section style={{ marginBottom: '40px' }}>
        <HeatmapGrid
          data={endpointHeatmap}
          labelKey="endpoint"
          title="API Reliability Heatmap (DASH-03)"
        />
      </section>

      <section style={{ marginBottom: '40px' }}>
        <HeatmapGrid
          data={flakinessData}
          labelKey="test_full_title"
          title="Flakiness Heatmap (DASH-04)"
        />
      </section>

      <section style={{ marginBottom: '40px' }}>
        <h3 style={{ marginBottom: '16px' }}>Retry Impact (DASH-05)</h3>
        <RetryImpactChart tests={tests} />
      </section>
    </div>
  )
}

/** Labeled field display. */
function Field({ label, value, mono = false }) {
  return (
    <div>
      <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '2px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {label}
      </div>
      <div style={{ fontFamily: mono ? 'monospace' : 'inherit', fontSize: '14px', fontWeight: 500 }}>
        {String(value)}
      </div>
    </div>
  )
}
