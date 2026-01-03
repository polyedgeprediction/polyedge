export function Header() {
  return (
    <header style={{ 
      height: '56px', 
      borderBottom: '1px solid #1f1f1f', 
      backgroundColor: '#0f0f0f',
      padding: '0 24px',
      display: 'flex',
      alignItems: 'center'
    }}>
      <span style={{ fontSize: '18px', fontWeight: '600', color: '#f9fafb' }}>
        polyedge
      </span>
    </header>
  )
}
