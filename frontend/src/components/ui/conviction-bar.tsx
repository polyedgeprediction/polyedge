import { cn } from '@/lib/utils'

interface ConvictionBarProps {
  value: number
  label?: string
  showLabel?: boolean
  size?: 'sm' | 'md'
  variant?: 'profit' | 'loss' | 'neutral'
}

export function ConvictionBar({
  value,
  label,
  showLabel = true,
  size = 'md',
  variant = 'profit',
}: ConvictionBarProps) {
  const clampedValue = Math.max(0, Math.min(100, value))

  return (
    <div className="w-full">
      {showLabel && (
        <div className="flex justify-between items-center mb-1">
          {label && <span className="text-xs text-muted">{label}</span>}
          <span className="text-xs font-mono text-secondary">
            {clampedValue.toFixed(0)}%
          </span>
        </div>
      )}
      <div
        className={cn(
          "w-full bg-subtle rounded-full overflow-hidden",
          size === "sm" ? "h-1.5" : "h-2"
        )}
      >
        <div
          className={cn(
            "h-full rounded-full transition-all duration-500 ease-out",
            variant === "profit" && "bg-profit",
            variant === "loss" && "bg-loss",
            variant === "neutral" && "bg-accent"
          )}
          style={{ width: `${clampedValue}%` }}
        />
      </div>
    </div>
  )
}
