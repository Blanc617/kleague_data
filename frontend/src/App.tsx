import { Routes, Route, Navigate } from 'react-router-dom'
import AppLayout from './components/AppLayout'
import HomePage from './pages/HomePage'
import ChatPage from './pages/ChatPage'
import StatsPage from './pages/StatsPage'
import BriefingPage from './pages/BriefingPage'
import SchedulePage from './pages/SchedulePage'
import StandingsPage from './pages/StandingsPage'
import PlayerPage from './pages/PlayerPage'
import PlayerComparePage from './pages/PlayerComparePage'
import AnalyticsPage from './pages/AnalyticsPage'
import './index.css'

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/stats" element={<StatsPage />} />
        <Route path="/briefing" element={<BriefingPage />} />
        <Route path="/schedule" element={<SchedulePage />} />
        <Route path="/standings" element={<StandingsPage />} />
        <Route path="/player" element={<PlayerPage />} />
        <Route path="/compare" element={<PlayerComparePage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
