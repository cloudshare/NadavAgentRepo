/**
 * HeatmapGrid — CSS table heatmap component.
 *
 * NOT a Recharts component. Recharts has no native heatmap.
 * Uses HTML table with HSL background on heat bars.
 *
 * Props:
 *   data: array of objects, each with at least { [labelKey]: string, failure_rate: number }
 *   labelKey: string — which field to use as the row label (e.g. "endpoint" or "test_full_title")
 *   title: optional string — section heading
 */
export function HeatmapGrid({ data, labelKey = 'endpoint', title }) {
  if (!data || data.length === 0) {
    return (
      <div>
        {title && <h3 style={{ marginBottom: '12px' }}>{title}</h3>}
        <p style={{ color: '#9ca3af' }}>No data available.</p>
      </div>
    )
  }

  return (
    <div>
      {title && <h3 style={{ marginBottom: '12px' }}>{title}</h3>}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: '13px' }}>
          <thead>
            <tr style={{ background: '#f3f4f6', borderBottom: '2px solid #e5e7eb' }}>
              <th style={{ textAlign: 'left', padding: '8px 12px', fontWeight: 600 }}>
                {labelKey === 'endpoint' ? 'Endpoint' : 'Test'}
              </th>
              {data[0]?.total_failing_tests !== undefined && (
                <th style={{ textAlign: 'right', padding: '8px 12px', fontWeight: 600 }}>Failing Tests</th>
              )}
              {data[0]?.failure_count !== undefined && (
                <th style={{ textAlign: 'right', padding: '8px 12px', fontWeight: 600 }}>Failures</th>
              )}
              {data[0]?.total_runs !== undefined && (
                <th style={{ textAlign: 'right', padding: '8px 12px', fontWeight: 600 }}>Total Runs</th>
              )}
              <th style={{ textAlign: 'right', padding: '8px 12px', fontWeight: 600 }}>Rate</th>
              <th style={{ padding: '8px 12px', fontWeight: 600, width: '200px' }}>Heat</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => {
              const rate = row.failure_rate ?? 0
              // HSL color: hue 0=red (rate=1.0), hue 120=green (rate=0.0)
              const hue = Math.round(120 * (1 - rate))
              const heatColor = `hsl(${hue}, 70%, 52%)`
              const barWidth = Math.max(4, Math.round(rate * 180))

              return (
                <tr
                  key={row[labelKey] ?? i}
                  style={{ borderBottom: '1px solid #f3f4f6' }}
                >
                  <td style={{
                    padding: '8px 12px',
                    fontFamily: 'monospace',
                    fontSize: '12px',
                    maxWidth: '400px',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}>
                    {row[labelKey] ?? '(unknown)'}
                  </td>
                  {row.total_failing_tests !== undefined && (
                    <td style={{ textAlign: 'right', padding: '8px 12px' }}>
                      {row.total_failing_tests}
                    </td>
                  )}
                  {row.failure_count !== undefined && (
                    <td style={{ textAlign: 'right', padding: '8px 12px' }}>
                      {row.failure_count}
                    </td>
                  )}
                  {row.total_runs !== undefined && (
                    <td style={{ textAlign: 'right', padding: '8px 12px' }}>
                      {row.total_runs}
                    </td>
                  )}
                  <td style={{ textAlign: 'right', padding: '8px 12px' }}>
                    {(rate * 100).toFixed(1)}%
                  </td>
                  <td style={{ padding: '8px 12px' }}>
                    <div
                      title={`${(rate * 100).toFixed(1)}% failure rate`}
                      style={{
                        width: `${barWidth}px`,
                        height: '16px',
                        background: heatColor,
                        borderRadius: '3px',
                        minWidth: '4px',
                      }}
                    />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
