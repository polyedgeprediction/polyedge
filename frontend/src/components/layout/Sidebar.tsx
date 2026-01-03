import { NavLink, useLocation } from 'react-router-dom'

const navigation = [
  { name: 'Dashboard', href: '/app' },
]

const reports = [
  { name: 'Smart Money', href: '/app/reports/smartmoney/concentration' },
]

export function Sidebar() {
  const location = useLocation()

  const isActiveLink = (href: string) => {
    return location.pathname === href
  }
  
  return (
    <aside style={{ 
      width: '224px', 
      borderRight: '1px solid #1f1f1f', 
      backgroundColor: '#0f0f0f',
      minHeight: 'calc(100vh - 56px)',
      padding: '16px',
      flexShrink: 0
    }}>
      <nav style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {navigation.map((item) => {
          const isActive = isActiveLink(item.href)
          return (
            <NavLink
              key={item.href}
              to={item.href}
              style={{
                padding: '8px 12px',
                borderRadius: '6px',
                color: isActive ? '#f9fafb' : '#9ca3af',
                backgroundColor: isActive ? '#1a1a1a' : 'transparent',
                textDecoration: 'none',
                fontSize: '14px'
              }}
            >
              {item.name}
            </NavLink>
          )
        })}
      </nav>

      <div style={{ marginTop: '24px' }}>
        <div style={{ 
          padding: '0 12px', 
          marginBottom: '8px', 
          fontSize: '11px', 
          fontWeight: 500,
          color: '#71717a',
          textTransform: 'uppercase',
          letterSpacing: '0.05em'
        }}>
          Reports
        </div>
        <nav style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {reports.map((item) => {
            const isActive = isActiveLink(item.href)
            return (
              <NavLink
                key={item.href}
                to={item.href}
                style={{
                  padding: '8px 12px',
                  borderRadius: '6px',
                  color: isActive ? '#f9fafb' : '#9ca3af',
                  backgroundColor: isActive ? '#1a1a1a' : 'transparent',
                  textDecoration: 'none',
                  fontSize: '14px'
                }}
              >
                {item.name}
              </NavLink>
            )
          })}
        </nav>
      </div>
    </aside>
  )
}
