import { Routes, Route } from 'react-router-dom'
import SDLCDashboard from '@/pipeline/SDLCDashboard'
import NotFoundPage from '@/pages/NotFoundPage'

// The AutoFlow pipeline dashboard is a full-screen experience (its own header
// and landing screen), so it renders full-bleed rather than inside the shared
// Header/Footer chrome. Routing stays here as the app shell.
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<SDLCDashboard />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
