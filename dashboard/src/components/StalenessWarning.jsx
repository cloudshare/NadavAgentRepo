/**
 * StalenessWarning — KG-03 requirement.
 * Displays a yellow warning banner when the knowledge graph is >= 7 days old.
 * If kgData is null or days_old < 7, renders nothing.
 *
 * Props:
 *   kgData: { last_updated: string, days_old: number } | null
 */
export function StalenessWarning({ kgData }) {
  if (!kgData) return null
  const { days_old, last_updated } = kgData
  if (days_old < 7) return null
  return (
    <div
      role="alert"
      style={{
        background: '#fef3c7',
        border: '1px solid #f59e0b',
        borderRadius: '4px',
        padding: '10px 16px',
        marginBottom: '24px',
        fontSize: '14px',
        color: '#92400e',
      }}
    >
      <strong>Knowledge graph is {days_old} days old</strong> (last crawled: {last_updated}).
      Results may not reflect recent CloudShare API changes.
      Run <code style={{ background: '#fde68a', padding: '1px 4px', borderRadius: '2px' }}>python -m src.knowledge_graph.crawler</code> to refresh.
    </div>
  )
}
