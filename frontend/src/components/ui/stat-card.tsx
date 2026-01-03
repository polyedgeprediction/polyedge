import { cn } from '@/lib/utils'
import { TrendingUp, TrendingDown } from 'lucide-react'

interface StatCardProps {
  label: string
  value: string | number
  valueClassName?: string
  change?: number
  changeLabel?: string
}

export function StatCard({
  label,
  value,
  valueClassName,
  change,
  changeLabel,
}: StatCardProps) {
  return (
    <div className="bg-surface border border-border-subtle rounded-lg p-4">
      <div className="text-sm text-muted mb-1">{label}</div>
      <div
        className={cn(
          "text-2xl font-semibold font-mono tabular-nums",
          valueClassName || "text-primary"
        )}
      >
        {value}
      </div>
      {change !== undefined && (
        <div className="flex items-center gap-1 mt-1 text-xs">
          {change >= 0 ? (
            <TrendingUp className="w-3 h-3 text-profit" />
          ) : (
            <TrendingDown className="w-3 h-3 text-loss" />
          )}
          <span className={change >= 0 ? "text-profit" : "text-loss"}>
            {change >= 0 ? "+" : ""}{change}%
          </span>
          {changeLabel && <span className="text-muted">{changeLabel}</span>}
        </div>
      )}
    </div>
  )
}
