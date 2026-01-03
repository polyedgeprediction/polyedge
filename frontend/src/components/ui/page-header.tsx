interface PageHeaderProps {
  title: string
  description?: string
  action?: React.ReactNode
  meta?: string
}

export function PageHeader({ title, description, action, meta }: PageHeaderProps) {
  return (
    <div className="mb-8">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-primary">{title}</h1>
          {description && (
            <p className="text-sm text-muted mt-1">{description}</p>
          )}
        </div>
        {action}
      </div>
      {meta && <p className="text-xs text-muted mt-2">{meta}</p>}
    </div>
  )
}

