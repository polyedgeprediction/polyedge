import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from './components/layout/Layout'
import { Dashboard } from './pages/Dashboard'
import SmartMoney from './pages/reports/SmartMoney'
import MarketLevels from './pages/reports/MarketLevels'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Redirect root to /app */}
        <Route path="/" element={<Navigate to="/app" replace />} />
        
        {/* Redirect old paths to new /app paths */}
        <Route path="/reports/smartmoney/concentration" element={<Navigate to="/app/reports/smartmoney/concentration" replace />} />
        
        {/* Main app routes */}
        <Route path="/app" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="reports/smartmoney/concentration" element={<SmartMoney />} />
          <Route path="reports/smartmoney/concentration/market/:marketId/levels" element={<MarketLevels />} />
        </Route>

        {/* Catch-all redirect */}
        <Route path="*" element={<Navigate to="/app" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
