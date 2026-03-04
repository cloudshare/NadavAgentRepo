import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'

/**
 * RetryImpactChart — DASH-05.
 * Shows tests that passed on retry (retry_count > 0 AND status == "passed").
 *
 * Props:
 *   tests: array of test objects from report.tests
 */
export function RetryImpactChart({ tests }) {
  if (!tests || tests.length === 0) {
    return <p style={{ color: '#9ca3af' }}>No test data available.</p>
  }

  // Filter tests that passed after retrying
  const retryPassers = tests
    .filter((t) => (t.retry_count ?? 0) > 0 && t.status === 'passed')
    .map((t) => ({
      name: t.test_title ?? t.full_title ?? 'Unknown',
      retries: t.retry_count ?? 1,
    }))
    .sort((a, b) => b.retries - a.retries)
    .slice(0, 20)  // cap at 20 for readability

  if (retryPassers.length === 0) {
    return <p style={{ color: '#9ca3af' }}>No tests passed on retry in this run.</p>
  }

  return (
    <ResponsiveContainer width="100%" height={Math.max(200, retryPassers.length * 28)}>
      <BarChart
        data={retryPassers}
        layout="vertical"
        margin={{ top: 0, right: 30, left: 20, bottom: 0 }}
      >
        <XAxis type="number" allowDecimals={false} label={{ value: 'Retry Count', position: 'insideBottom', offset: -4 }} />
        <YAxis
          type="category"
          dataKey="name"
          width={200}
          tick={{ fontSize: 11, fontFamily: 'monospace' }}
        />
        <Tooltip />
        <Bar dataKey="retries" fill="#f59e0b" name="Retries to Pass">
          {retryPassers.map((_, index) => (
            <Cell key={index} fill="#f59e0b" />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
