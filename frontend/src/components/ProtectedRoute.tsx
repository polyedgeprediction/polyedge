import { Navigate } from 'react-router-dom'
import { useAuth } from '@/lib/auth'

interface Props {
  children: React.ReactNode
}

export function ProtectedRoute({ children }: Props) {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen bg-base flex items-center justify-center">
        <div className="text-muted">Loading...</div>
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}
