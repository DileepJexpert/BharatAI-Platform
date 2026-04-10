import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Chat from './pages/Chat'
import Conversations from './pages/Conversations'
import Models from './pages/Models'
import DomainDetails from './pages/DomainDetails'
import SettingsPage from './pages/Settings'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/conversations" element={<Conversations />} />
        <Route path="/models" element={<Models />} />
        <Route path="/domain/:domainId" element={<DomainDetails />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  )
}
