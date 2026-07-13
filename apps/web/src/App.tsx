import { Routes, Route } from 'react-router-dom'
import Header from '@/components/Header'
import Footer from '@/components/Footer'
import DashboardPage from '@/pages/DashboardPage'
import RequirementsPage from '@/pages/RequirementsPage'
import DesignPage from '@/pages/DesignPage'
import ImplementationPage from '@/pages/ImplementationPage'
import TestingPage from '@/pages/TestingPage'
import NotFoundPage from '@/pages/NotFoundPage'

export default function App() {
  return (
    <div className="min-h-screen flex flex-col bg-surface">
      <Header />
      <main className="flex-1 container mx-auto px-4 py-8">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/requirements" element={<RequirementsPage />} />
          <Route path="/design" element={<DesignPage />} />
          <Route path="/implementation" element={<ImplementationPage />} />
          <Route path="/testing" element={<TestingPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
      <Footer />
    </div>
  )
}
