import { useEffect, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { api } from './api'
import { AppShell } from './components/AppShell'
import { DeleteAnalysisPage } from './pages/DeleteAnalysisPage'
import { AnalysisPage } from './pages/AnalysisPage'
import { MethodologyPage } from './pages/MethodologyPage'
import { NewAnalysisPage } from './pages/NewAnalysisPage'
import { PlaybookPage } from './pages/PlaybookPage'
import { PortfolioPage } from './pages/PortfolioPage'
import { ScenarioPage } from './pages/ScenarioPage'

export default function App() {
  const [connected, setConnected] = useState(false)
  useEffect(() => {
    let active = true
    const probe = () => api.readiness().then(() => { if (active) setConnected(true) }).catch(() => { if (active) setConnected(false) })
    const handleOffline = () => setConnected(false)
    const handleVisibility = () => { if (document.visibilityState === 'visible') void probe() }
    void probe()
    const interval = window.setInterval(() => { void probe() }, 30_000)
    window.addEventListener('online', probe)
    window.addEventListener('offline', handleOffline)
    document.addEventListener('visibilitychange', handleVisibility)
    return () => {
      active = false
      window.clearInterval(interval)
      window.removeEventListener('online', probe)
      window.removeEventListener('offline', handleOffline)
      document.removeEventListener('visibilitychange', handleVisibility)
    }
  }, [])
  return <AppShell connected={connected}>
    <Routes>
      <Route path="/" element={<PortfolioPage connected={connected} />} />
      <Route path="/new" element={<NewAnalysisPage connected={connected} />} />
      <Route path="/analysis/:analysisId" element={<AnalysisPage connected={connected} />} />
      <Route path="/analysis/:analysisId/delete" element={<DeleteAnalysisPage connected={connected} />} />
      <Route path="/analysis/:analysisId/scenarios" element={<ScenarioPage connected={connected} />} />
      <Route path="/analysis/:analysisId/playbook" element={<PlaybookPage connected={connected} />} />
      <Route path="/methodology" element={<MethodologyPage connected={connected} />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  </AppShell>
}
