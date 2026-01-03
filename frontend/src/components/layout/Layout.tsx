import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Header } from './Header'
import { Sidebar } from './Sidebar'

export function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#0a0a0a', position: 'relative' }}>
      <Header />
      <div style={{ display: 'flex' }}>
        {sidebarOpen && <Sidebar />}
        <main style={{ flex: 1, padding: '24px' }}>
          <Outlet />
        </main>
      </div>
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        style={{
          position: 'fixed',
          bottom: '24px',
          left: '24px',
          background: '#1f1f1f',
          border: '1px solid #2f2f2f',
          borderRadius: '8px',
          color: '#f9fafb',
          cursor: 'pointer',
          padding: '12px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          boxShadow: '0 4px 6px rgba(0, 0, 0, 0.3)'
        }}
        title="Toggle sidebar"
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <line x1="3" y1="12" x2="21" y2="12"></line>
          <line x1="3" y1="6" x2="21" y2="6"></line>
          <line x1="3" y1="18" x2="21" y2="18"></line>
        </svg>
      </button>
    </div>
  )
}
