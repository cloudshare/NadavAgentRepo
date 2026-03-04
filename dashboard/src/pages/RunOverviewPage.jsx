import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts'
import { getRun, getKgStaleness } from '../api'
import { StalenessWarning } from '../components/StalenessWarning'

// Color palette for pie chart slices
const RATIO_COLORS = {
  infra: '#e05252',
  app: '#f59e0b',
  test_design: '#3b82f6',
  uncertain: '#9ca3af',
}

// Human-readable labels for ratio buckets
const RATIO_LABELS = {
  infra: 'Infrastructure',
  app: 'Application',
  test_design: 'Test Design',
  uncertain: 'Uncertain',
}

export default function RunOverviewPage() {
  const { runId } = useParams()
  const [runData, setRunData] = useState(null)
  const [kgData, setKgData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([getRun(runId), getKgStaleness()])
      .then(([run, kg]) => {
        setRunData(run)
        setKgData(kg)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [runId])

  if (loading) {
    return <div style={{ padding: '40px', fontFamily: 'sans-serif' }}>Loading run data...</div>
  }

  if (error) {
    return (
      <div style={{ padding: '40px', fontFamily: 'sans-serif', color: '#dc2626' }}>
        Error loading run: {error}
      </div>
    )
  }

  if (!runData) return null

  const passCount = (runData.total_tests ?? 0) - (runData.failed_tests ?? 0)
  const failCount = runData.failed_tests ?? 0
  const totalCount = runData.total_tests ?? 0

  // Build bar chart data from report.summary.by_category dict
  const byCategory = runData.report?.summary?.by_category ?? {}
  const categoryChartData = Object.entries(byCategory)
    .map(([category, count]) => ({ category, count }))
    .sort((a, b) => b.count - a.count)

  // Build pie chart data from report.failure_ratios.counts
  const ratioCounts = runData.report?.failure_ratios?.counts ?? {}
  const pieData = Object.entries(ratioCounts)
    .filter(([, value]) => value > 0)
    .map(([name, value]) => ({ name, label: RATIO_LABELS[name] ?? name, value }))

  const costFormatted = runData.estimated_cost_usd != null
    ? `$${runData.estimated_cost_usd.toFixed(4)}`
    : 'N/A'

  return (
    <div style={{ maxWidth: '960px', margin: '40px auto', padding: '0 20px', fontFamily: 'sans-serif' }}>
      {/* Navigation */}
      <Link to="/" style={{ color: '#2563eb', fontSize: '14px' }}>← Back to Landing</Link>

      <h1 style={{ marginTop: '16px', marginBottom: '4px' }}>Run Overview</h1>
      <p style={{ color: '#6b7280', fontFamily: 'monospace', fontSize: '13px', marginBottom: '24px' }}>
        {runId}
      </p>

      {/* KG staleness banner — always render component; it decides visibility (KG-03) */}
      <StalenessWarning kgData={kgData} />

      {/* Summary cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '40px' }}>
        <StatCard label="Total Tests" value={totalCount} />
        <StatCard label="Passed" value={passCount} color="#16a34a" />
        <StatCard label="Failed" value={failCount} color={failCount > 0 ? '#dc2626' : '#16a34a'} />
        <StatCard label="Run Cost" value={costFormatted} />
      </div>

      {/* Bar chart: failure by category */}
      <section style={{ marginBottom: '48px' }}>
        <h2 style={{ marginBottom: '16px' }}>Failures by Category</h2>
        {categoryChartData.length === 0 ? (
          <p style={{ color: '#9ca3af' }}>No failures in this run.</p>
        ) : (
          <ResponsiveContainer width="100%" height={320}>
            <BarChart
              data={categoryChartData}
              margin={{ top: 5, right: 20, left: 0, bottom: 70 }}
            >
              <XAxis
                dataKey="category"
                angle={-35}
                textAnchor="end"
                interval={0}
                tick={{ fontSize: 12 }}
              />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="count" fill="#e05252" name="Failures" />
            </BarChart>
          </ResponsiveContainer>
        )}
      </section>

      {/* Pie chart: infra/app/test_design/uncertain ratio */}
      <section style={{ marginBottom: '48px' }}>
        <h2 style={{ marginBottom: '16px' }}>Failure Origin Breakdown</h2>
        {pieData.length === 0 ? (
          <p style={{ color: '#9ca3af' }}>No classified failures.</p>
        ) : (
          <ResponsiveContainer width="100%" height={320}>
            <PieChart>
              <Pie
                data={pieData}
                dataKey="value"
                nameKey="label"
                cx="50%"
                cy="50%"
                outerRadius={120}
                label={({ label, percent }) => `${label}: ${(percent * 100).toFixed(0)}%`}
              >
                {pieData.map((entry) => (
                  <Cell
                    key={entry.name}
                    fill={RATIO_COLORS[entry.name] ?? '#6b7280'}
                  />
                ))}
              </Pie>
              <Tooltip formatter={(value, name) => [value, name]} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        )}
      </section>

      {/* Link to detailed views (implemented in 05-03) */}
      <section>
        <h2 style={{ marginBottom: '16px' }}>Detailed Analysis</h2>
        <p>
          <Link to={`/runs/${runId}/tests/0`}>View per-test drill-down, heatmaps, and retry analysis →</Link>
        </p>
      </section>
    </div>
  )
}

/** Small stat display card. */
function StatCard({ label, value, color }) {
  return (
    <div style={{
      background: '#f9fafb',
      border: '1px solid #e5e7eb',
      borderRadius: '8px',
      padding: '16px',
      textAlign: 'center',
    }}>
      <div style={{ fontSize: '28px', fontWeight: 700, color: color ?? '#111827' }}>
        {value}
      </div>
      <div style={{ fontSize: '13px', color: '#6b7280', marginTop: '4px' }}>
        {label}
      </div>
    </div>
  )
}
