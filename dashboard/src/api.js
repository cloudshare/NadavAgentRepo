const BASE = '/api'

export async function startRun(testFolder, logFolder) {
  const res = await fetch(`${BASE}/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ test_folder: testFolder, log_folder: logFolder }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getRun(runId) {
  const res = await fetch(`${BASE}/runs/${runId}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function listRuns() {
  const res = await fetch(`${BASE}/runs`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getKgStaleness() {
  const res = await fetch(`${BASE}/kg-staleness`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
