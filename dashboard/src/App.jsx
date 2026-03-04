import { Routes, Route } from 'react-router'
import LandingPage from './pages/LandingPage'
import RunOverviewPage from './pages/RunOverviewPage'
import TestDrillDown from './pages/TestDrillDown'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/runs/:runId" element={<RunOverviewPage />} />
      <Route path="/runs/:runId/tests/:testIndex" element={<TestDrillDown />} />
    </Routes>
  )
}
