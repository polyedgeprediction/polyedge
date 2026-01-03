# Claude Code Prompt Templates

Copy-paste these prompts when working with Claude Code to generate consistent UI.

---

## 🚀 Session Start Prompt (Use First!)

```
I'm building a trading analytics dashboard. Before generating any code, read and internalize these design constraints:

PROJECT: PolyMarket Analytics
STACK: Vite + React + TypeScript + Tailwind + shadcn/ui

CRITICAL RULES:
1. Dark theme only - backgrounds: bg-base, bg-surface, bg-elevated, bg-subtle
2. All numbers must use: font-mono tabular-nums
3. Profit = text-profit (green), Loss = text-loss (red) - NO EXCEPTIONS
4. Use shadcn components when available (Button, Card, Badge, Input, Select)
5. Import from @/ aliases (@/components, @/lib, @/pages)
6. Use lucide-react for all icons
7. Keep it dense - minimal whitespace, data-first design

COLOR CLASSES:
- Backgrounds: bg-base, bg-surface, bg-elevated, bg-subtle
- Text: text-primary, text-secondary, text-muted
- Borders: border-border-subtle, border-border-default
- Semantic: text-profit, text-loss, text-accent, bg-profit-bg, bg-loss-bg

Acknowledge these constraints.
```

---

## Component Prompts

### New Custom Component

```
Create a [ComponentName] component.

Location: src/components/ui/[component-name].tsx

Requirements:
- [Requirement 1]
- [Requirement 2]
- TypeScript with interface for props
- Use cn() from @/lib/utils for conditional classes
- Follow the design system colors

Props:
interface [ComponentName]Props {
  [prop]: [type]
}

Example usage:
<[ComponentName] [prop]={value} />
```

### Data Table Component

```
Create a table component for displaying [data type].

Location: src/components/[feature]/[TableName].tsx

Columns:
1. [Column] - [alignment: left/right] - [description]
2. [Column] - [alignment: left/right] - [description]
3. [Column] - [alignment: left/right] - [description]

Data interface:
interface [DataType] {
  [field]: [type]
}

Requirements:
- Header row: text-xs uppercase tracking-wide text-muted font-medium
- Number columns: text-right font-mono tabular-nums
- PnL values: Use <PnLValue /> component
- Row hover: hover:bg-elevated transition-colors
- Clickable rows (optional): cursor-pointer + onClick handler
```

### Chart Component

```
Create a [chart type] chart component.

Location: src/components/charts/[ChartName].tsx

Requirements:
- Use Recharts library
- Dark theme colors:
  - Grid: #27272a
  - Axis text: #71717a  
  - Profit line: #22c55e
  - Loss line: #ef4444
  - Accent: #3b82f6
- Responsive width
- Custom tooltip with dark styling

Data shape:
interface ChartData {
  [xField]: [type]
  [yField]: [type]
}
```

---

## Page Prompts

### New Report Page

```
Create a report page for [Report Name].

Location: src/pages/reports/[PageName].tsx

Structure:
1. PageHeader with title "[Title]" and description
2. Stats row with 4 StatCards:
   - [Stat 1]
   - [Stat 2]
   - [Stat 3]
   - [Stat 4]
3. Optional filter row (Select, Button)
4. Main content card with table

API endpoint: GET /api/reports/[endpoint]/
Response type: (define the interface)

Data fetching pattern:
- useState for data, loading, error
- useEffect to fetch on mount
- Handle loading and error states

Include:
- Loading skeleton
- Error state with retry button
- Empty state if no data
```

### Detail Page

```
Create a detail page for [Entity].

Location: src/pages/[entity]/[EntityDetail].tsx
Route: /[entity]/:id

Sections:
1. Header with entity identifier
2. Stats row with key metrics
3. [Section 1]: [content]
4. [Section 2]: [content]

API: GET /api/[entity]/{id}/
Use useParams() to get the ID

Include back navigation to /[parent-route]
```

---

## Feature Prompts

### Add Data Fetching

```
Add data fetching to [Component/Page].

API endpoint: [method] /api/[endpoint]/
Response type: [interface]

Pattern:
const [data, setData] = useState<Type | null>(null)
const [loading, setLoading] = useState(true)
const [error, setError] = useState<string | null>(null)

useEffect(() => {
  fetchData()
    .then(setData)
    .catch(e => setError(e.message))
    .finally(() => setLoading(false))
}, [dependencies])

Handle all three states in the render.
```

### Add Filter/Search

```
Add filtering to [Component].

Filter options:
- [Filter 1]: [type] (dropdown/input/toggle)
- [Filter 2]: [type]

Requirements:
- Store filter state with useState
- Update API call when filters change
- Clear filters button
- Show active filter count
```

### Add Pagination

```
Add pagination to [Table/List].

Requirements:
- Page size: [number] items
- Show current page / total pages
- Previous/Next buttons
- Optional: Page number input

State:
- currentPage: number
- totalPages: number (from API)

API should accept: ?page=N&page_size=M
```

---

## Styling Prompts

### Add Loading State

```
Add loading skeleton to [Component].

Match the layout of the loaded state:
- Use bg-subtle for skeleton blocks
- Add animate-pulse
- Match heights of text/numbers

Pattern:
if (loading) {
  return (
    <div className="animate-pulse">
      <div className="h-4 bg-subtle rounded w-3/4 mb-2" />
      <div className="h-8 bg-subtle rounded w-1/2" />
    </div>
  )
}
```

### Add Empty State

```
Add empty state to [Component] when data is empty.

Show:
- Icon from lucide-react
- Heading: "[Empty state message]"
- Description: "[Helpful text]"
- Action button (optional)

Use text-muted for text, center alignment.
```

### Add Error State

```
Add error handling to [Component].

When error occurs:
- Show error message in bg-loss-bg container
- Include retry button
- Log error to console

Pattern:
if (error) {
  return (
    <div className="bg-loss-bg border border-loss/20 rounded-lg p-4">
      <div className="flex items-center gap-2 text-loss mb-2">
        <AlertCircle className="w-4 h-4" />
        <span className="font-medium">Error</span>
      </div>
      <p className="text-sm text-secondary">{error}</p>
      <Button variant="outline" size="sm" onClick={retry} className="mt-3">
        Try again
      </Button>
    </div>
  )
}
```

### Make Responsive

```
Make [Component/Page] responsive.

Breakpoints:
- Mobile (<768px): [layout description]
- Tablet (768-1024px): [layout description]
- Desktop (>1024px): current layout

Use Tailwind responsive prefixes: sm:, md:, lg:, xl:

For tables on mobile, consider:
- Horizontal scroll: overflow-x-auto
- Hide non-essential columns: hidden md:table-cell
- Card layout instead of table
```

---

## Refactoring Prompts

### Extract Component

```
Extract [section] from [File] into a reusable component.

New file: src/components/[folder]/[ComponentName].tsx

Props needed:
- [prop1]: [type]
- [prop2]: [type]

Keep styling identical. Make it reusable.
```

### Add TypeScript Types

```
Add TypeScript types to [Component/File].

Define interfaces for:
- Component props
- API response data
- Any complex objects

Put shared types in src/types/index.ts
```

---

## Quality Check Prompt

```
Review this component for design system compliance:

[paste component code]

Check:
1. Are colors using design tokens (not hardcoded hex)?
2. Are numbers using font-mono tabular-nums?
3. Is PnL colored correctly (profit=green, loss=red)?
4. Are imports using @/ aliases?
5. Is shadcn used where applicable?
6. Are loading/error states handled?

List violations and provide fixes.
```

---

## Quick Reference

### Common Imports

```tsx
// Components
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'

// Custom components
import { PnLValue } from '@/components/ui/pnl-value'
import { StatCard } from '@/components/ui/stat-card'
import { PageHeader } from '@/components/ui/page-header'
import { ConvictionBar } from '@/components/ui/conviction-bar'

// Utils
import { cn } from '@/lib/utils'
import { formatCurrency, formatPercent, formatAddress } from '@/lib/formatters'

// Icons
import { TrendingUp, TrendingDown, RefreshCw, AlertCircle } from 'lucide-react'

// Routing
import { useNavigate, useParams, NavLink } from 'react-router-dom'

// Auth
import { useAuth } from '@/lib/auth'

// API
import { reports, wallets } from '@/lib/api'
```

### Common Patterns

```tsx
// Card with title
<Card>
  <CardHeader>
    <CardTitle>Title</CardTitle>
  </CardHeader>
  <CardContent>
    {/* content */}
  </CardContent>
</Card>

// Stats row
<div className="grid grid-cols-4 gap-4 mb-6">
  <StatCard label="..." value="..." />
</div>

// Table structure
<div className="overflow-x-auto">
  <table className="w-full">
    <thead>
      <tr className="border-b border-border-subtle">
        <th className="text-left text-xs font-medium text-muted uppercase tracking-wide py-3 px-4">
          Header
        </th>
      </tr>
    </thead>
    <tbody className="divide-y divide-border-subtle">
      <tr className="hover:bg-elevated transition-colors">
        <td className="py-3 px-4 text-sm">Content</td>
      </tr>
    </tbody>
  </table>
</div>

// Conditional styling
className={cn(
  "base-classes",
  condition && "conditional-classes",
  value >= 0 ? "text-profit" : "text-loss"
)}
```