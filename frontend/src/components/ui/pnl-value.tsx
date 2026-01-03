import { cn } from '@/lib/utils'
import { formatCurrency } from '@/lib/formatters'

interface PnLValueProps {
  value: number | null | undefined
  size?: 'sm' | 'md' | 'lg' | 'xl'
  showSign?: boolean
  className?: string
}

const sizeClasses = {
  sm: 'text-sm',
  md: 'text-base',
  lg: 'text-lg',
  xl: 'text-2xl font-semibold',
}

export function PnLValue({ 
  value, 
  size = 'md', 
  showSign = true,
  className 
}: PnLValueProps) {
  if (value === null || value === undefined) {
    return <span className={cn("text-muted", className)}>—</span>
  }

  return (
    <span
      className={cn(
        "font-mono tabular-nums",
        sizeClasses[size],
        value >= 0 ? "text-profit" : "text-loss",
        className
      )}
    >
      {formatCurrency(value, showSign)}
    </span>
  )
}
