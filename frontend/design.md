# PolyMarket Analytics - Design System

> **This document is the single source of truth for all UI code.**
> Claude Code must reference this when generating any frontend components.

---

## 1. Tech Stack

```
Vite + React 18 + TypeScript
├── Tailwind CSS (styling)
├── shadcn/ui (component primitives)
├── React Router (routing)
├── Lucide React (icons)
└── Recharts (charts)
```

**Import Patterns:**
```tsx
// Components
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'

// Custom components
import { PnLValue } from '@/components/ui/pnl-value'
import { StatCard } from '@/components/ui/stat-card'

// Utilities
import { cn } from '@/lib/utils'
import { formatCurrency, formatPercent } from '@/lib/formatters'

// Icons (always from lucide-react)
import { TrendingUp, TrendingDown, RefreshCw } from 'lucide-react'

// Hooks
import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
```

---

## 2. Design Philosophy

| Principle | Implementation |
|-----------|----------------|
| **Data-first** | High information density, minimal whitespace |
| **Trust through precision** | Aligned numbers, consistent formatting |
| **Dark theme** | Reduces eye strain for data-heavy screens |
| **Color semantics** | Green = profit, Red = loss, Blue = action |
| **Professional restraint** | Subtle animations, no decorative elements |

---

## 3. Color System

### CSS Variables (defined in index.css)

```css
:root {
  /* Background layers (darkest to lightest) */
  --bg-base: 0 0% 4%;           /* #0a0a0b - Page background */
  --bg-surface: 0 0% 7%;         /* #111113 - Cards, panels */
  --bg-elevated: 0 0% 10%;       /* #1a1a1d - Hover states */
  --bg-subtle: 0 0% 14%;         /* #232326 - Input backgrounds */

  /* Text hierarchy */
  --text-primary: 0 0% 98%;      /* #fafafa - Main content */
  --text-secondary: 240 4% 65%;  /* #a1a1aa - Supporting text */
  --text-muted: 240 4% 46%;      /* #71717a - Disabled, hints */

  /* Borders */
  --border-subtle: 240 4% 16%;   /* #27272a - Card borders */
  --border-default: 240 4% 26%;  /* #3f3f46 - Input borders */

  /* Semantic colors */
  --profit: 142 71% 45%;         /* #22c55e - Gains */
  --profit-bg: 142 71% 45% / 0.08;
  --loss: 0 84% 60%;             /* #ef4444 - Losses */
  --loss-bg: 0 84% 60% / 0.08;
  --accent: 217 91% 60%;         /* #3b82f6 - Primary actions */
  --accent-hover: 217 91% 50%;   /* #2563eb - Hover state */
  --warning: 38 92% 50%;         /* #f59e0b - Caution */
  --info: 187 85% 43%;           /* #06b6d4 - Informational */
}
```

### Tailwind Usage

```tsx
// Backgrounds
className="bg-base"      // Page background
className="bg-surface"   // Cards
className="bg-elevated"  // Hover states, modals
className="bg-subtle"    // Input backgrounds

// Text
className="text-primary"    // Main content
className="text-secondary"  // Supporting
className="text-muted"      // Hints, disabled

// Borders
className="border-border-subtle"   // Card borders
className="border-border-default"  // Input borders

// Semantic
className="text-profit"     // Positive numbers
className="text-loss"       // Negative numbers
className="bg-profit-bg"    // Profit background tint
className="bg-loss-bg"      // Loss background tint
className="text-accent"     // Links, primary actions
className="bg-accent"       // Primary buttons
```

### ⚠️ Critical Rules

1. **Never hardcode colors** - Always use CSS variables via Tailwind
2. **Profit/Loss are sacred** - Only for financial gain/loss, never decoration
3. **Accent is for actions** - Buttons, links, interactive elements only

---

## 4. Typography

### Font Stack

```css
--font-sans: 'Inter', system-ui, sans-serif;
--font-mono: 'JetBrains Mono', 'SF Mono', Consolas, monospace;
```

### Scale

| Class | Size | Weight | Use Case |
|-------|------|--------|----------|
| `text-xs` | 12px | 400 | Labels, timestamps, badges |
| `text-sm` | 14px | 400 | Secondary info, table cells |
| `text-base` | 16px | 400 | Body text |
| `text-lg` | 18px | 500 | Section headers |
| `text-xl` | 20px | 600 | Card titles |
| `text-2xl` | 24px | 600 | Page titles |
| `text-3xl` | 30px | 700 | Hero numbers |

### ⚠️ Critical Rule: Tabular Numbers

**ALL financial figures MUST use monospace tabular numbers:**

```tsx
// ✅ CORRECT - Numbers align in columns
<span className="font-mono tabular-nums">$12,345.67</span>

// ❌ WRONG - Numbers misalign
<span>$12,345.67</span>
```

**Apply to:**
- Currency values
- Percentages
- Counts
- Any number in a table column

---

## 5. Spacing System

Use Tailwind's spacing scale consistently:

```
p-2  = 8px   → Tight (badges, small buttons)
p-3  = 12px  → Compact (table cells)
p-4  = 16px  → Default (card padding)
p-6  = 24px  → Spacious (section padding)

gap-2 = 8px  → Tight gaps
gap-4 = 16px → Default gaps
gap-6 = 24px → Section gaps

mb-1 = 4px   → Label to input
mb-4 = 16px  → Between card sections
mb-6 = 24px  → Between page sections
mb-8 = 32px  → Page header to content
```

---

## 6. Component Specifications

### 6.1 Card

```tsx
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'

// Basic usage
<Card>
  <CardHeader>
    <CardTitle>Title</CardTitle>
    <CardDescription>Optional subtitle</CardDescription>
  </CardHeader>
  <CardContent>
    {/* Content */}
  </CardContent>
</Card>

// With action button
<Card>
  <CardHeader className="flex flex-row items-center justify-between">
    <div>
      <CardTitle>Title</CardTitle>
      <CardDescription>Subtitle</CardDescription>
    </div>
    <Button variant="outline" size="sm">Action</Button>
  </CardHeader>
  <CardContent>
    {/* Content */}
  </CardContent>
</Card>
```

### 6.2 StatCard (Custom Component)

```tsx
// Usage
<StatCard 
  label="Total PnL"
  value="+$45,230"
  valueClassName="text-profit"
  change={12.5}
  changeLabel="vs last week"
/>

// Implementation pattern
<div className="bg-surface border border-border-subtle rounded-lg p-4">
  <div className="text-sm text-muted mb-1">{label}</div>
  <div className={cn(
    "text-2xl font-semibold font-mono tabular-nums",
    valueClassName || "text-primary"
  )}>
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
      <span className="text-muted">{changeLabel}</span>
    </div>
  )}
</div>
```

### 6.3 PnLValue (Custom Component)

```tsx
// Usage
<PnLValue value={12345.67} />           // +$12,345.67 in green
<PnLValue value={-5432.10} />           // -$5,432.10 in red
<PnLValue value={99999} size="xl" />    // Large hero number

// Implementation pattern
<span className={cn(
  "font-mono tabular-nums",
  sizeClasses[size],
  value >= 0 ? "text-profit" : "text-loss"
)}>
  {formatCurrency(value)}
</span>
```

### 6.4 Data Table

```tsx
// Table structure
<div className="overflow-x-auto">
  <table className="w-full">
    <thead>
      <tr className="border-b border-border-subtle">
        <th className="text-left text-xs font-medium text-muted uppercase tracking-wide py-3 px-4">
          Column Header
        </th>
        <th className="text-right text-xs font-medium text-muted uppercase tracking-wide py-3 px-4">
          Numeric Column
        </th>
      </tr>
    </thead>
    <tbody className="divide-y divide-border-subtle">
      <tr className="hover:bg-elevated transition-colors">
        <td className="py-3 px-4 text-sm text-primary">
          Text content
        </td>
        <td className="py-3 px-4 text-sm font-mono tabular-nums text-right">
          <PnLValue value={1234.56} />
        </td>
      </tr>
    </tbody>
  </table>
</div>
```

**Table Rules:**
- Headers: `text-xs uppercase tracking-wide text-muted font-medium`
- Text columns: `text-left`
- Number columns: `text-right font-mono tabular-nums`
- Row hover: `hover:bg-elevated transition-colors`
- Clickable rows: Add `cursor-pointer`

### 6.5 Badge

```tsx
import { Badge } from '@/components/ui/badge'

// Variants to create:
<Badge variant="default">Category</Badge>     // bg-elevated text-secondary
<Badge variant="profit">Active</Badge>        // bg-profit-bg text-profit
<Badge variant="loss">Closed</Badge>          // bg-loss-bg text-loss
<Badge variant="warning">Pending</Badge>      // bg-amber-500/10 text-amber-500
<Badge variant="info">New</Badge>             // bg-cyan-500/10 text-cyan-500
```

### 6.6 Button

```tsx
import { Button } from '@/components/ui/button'

// Primary action
<Button>Generate Report</Button>

// Secondary action
<Button variant="outline">Export CSV</Button>

// Ghost/subtle action
<Button variant="ghost">View Details</Button>

// Destructive action
<Button variant="destructive">Delete</Button>

// With icon
<Button>
  <RefreshCw className="w-4 h-4 mr-2" />
  Refresh
</Button>

// Icon only
<Button variant="ghost" size="icon">
  <RefreshCw className="w-4 h-4" />
</Button>
```

### 6.7 Input & Select

```tsx
import { Input } from '@/components/ui/input'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'

// Input
<div>
  <label className="block text-sm text-secondary mb-1">Label</label>
  <Input 
    type="text" 
    placeholder="Placeholder..."
    className="bg-elevated"
  />
</div>

// Select
<Select value={value} onValueChange={setValue}>
  <SelectTrigger className="w-48 bg-elevated">
    <SelectValue placeholder="Select..." />
  </SelectTrigger>
  <SelectContent>
    <SelectItem value="all">All Categories</SelectItem>
    <SelectItem value="politics">Politics</SelectItem>
    <SelectItem value="crypto">Crypto</SelectItem>
  </SelectContent>
</Select>
```

### 6.8 Conviction Bar (Custom)

```tsx
// Usage
<ConvictionBar value={75} label="YES" variant="profit" />

// Implementation
<div className="w-full">
  <div className="flex justify-between items-center mb-1">
    <span className="text-xs text-muted">{label}</span>
    <span className="text-xs font-mono text-secondary">{value}%</span>
  </div>
  <div className="w-full h-2 bg-subtle rounded-full overflow-hidden">
    <div 
      className={cn(
        "h-full rounded-full transition-all duration-500",
        variant === "profit" ? "bg-profit" : 
        variant === "loss" ? "bg-loss" : "bg-accent"
      )}
      style={{ width: `${value}%` }}
    />
  </div>
</div>
```

---

## 7. Layout Patterns

### Page Structure

```tsx
export default function ReportPage() {
  return (
    <div>
      {/* Page Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-primary">Page Title</h1>
        <p className="text-sm text-muted mt-1">Page description</p>
      </div>

      {/* KPI Stats Row */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <StatCard label="..." value="..." />
        <StatCard label="..." value="..." />
        <StatCard label="..." value="..." />
        <StatCard label="..." value="..." />
      </div>

      {/* Filters Row (optional) */}
      <div className="flex items-center gap-4 mb-4">
        <Select>...</Select>
        <Button variant="outline">...</Button>
      </div>

      {/* Main Content */}
      <Card>
        <CardHeader>
          <CardTitle>Section Title</CardTitle>
        </CardHeader>
        <CardContent>
          {/* Table or other content */}
        </CardContent>
      </Card>
    </div>
  )
}
```

### Grid Patterns

```tsx
// 4-column KPI row
<div className="grid grid-cols-4 gap-4">

// 3-column layout
<div className="grid grid-cols-3 gap-6">

// Main + Sidebar (8 + 4)
<div className="grid grid-cols-12 gap-6">
  <div className="col-span-8">{/* Main */}</div>
  <div className="col-span-4">{/* Sidebar */}</div>
</div>

// Stacked sections
<div className="space-y-6">
  <Card>...</Card>
  <Card>...</Card>
</div>

// Responsive: 1 col mobile, 2 cols tablet, 4 cols desktop
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
```

### App Layout (Layout.tsx)

```tsx
export function Layout() {
  return (
    <div className="min-h-screen bg-base">
      <Header />
      <div className="flex">
        <Sidebar />
        <main className="flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
```

---

## 8. Data Formatting

### formatters.ts

```typescript
// Currency with sign
export function formatCurrency(value: number, showSign = true): string {
  if (value === null || value === undefined) return '—';
  const prefix = showSign && value >= 0 ? '+' : '';
  const formatted = Math.abs(value).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${prefix}$${formatted}`;
}

// Percentage with sign
export function formatPercent(value: number, decimals = 1): string {
  if (value === null || value === undefined) return '—';
  const prefix = value >= 0 ? '+' : '';
  return `${prefix}${value.toFixed(decimals)}%`;
}

// Compact large numbers
export function formatCompact(value: number): string {
  if (Math.abs(value) >= 1e9) return `${(value / 1e9).toFixed(1)}B`;
  if (Math.abs(value) >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (Math.abs(value) >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
  return value.toFixed(0);
}

// Wallet address
export function formatAddress(address: string): string {
  if (!address || address.length <= 10) return address || '—';
  return `${address.slice(0, 6)}...${address.slice(-4)}`;
}

// Relative time
export function formatRelativeTime(date: Date | string): string {
  const now = new Date();
  const then = new Date(date);
  const diffMs = now.getTime() - then.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  
  return then.toLocaleDateString('en-US', { 
    month: 'short', 
    day: 'numeric' 
  });
}
```

---

## 9. Chart Specifications

### Colors

```typescript
const chartColors = {
  profit: '#22c55e',
  loss: '#ef4444',
  accent: '#3b82f6',
  neutral: '#71717a',
  grid: '#27272a',
  axis: '#71717a',
};
```

### Area Chart (PnL Over Time)

```tsx
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

<ResponsiveContainer width="100%" height={300}>
  <AreaChart data={data}>
    <defs>
      <linearGradient id="profitGradient" x1="0" y1="0" x2="0" y2="1">
        <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3}/>
        <stop offset="95%" stopColor="#22c55e" stopOpacity={0}/>
      </linearGradient>
    </defs>
    <XAxis 
      dataKey="date" 
      stroke="#71717a" 
      fontSize={12}
      tickLine={false}
      axisLine={false}
    />
    <YAxis 
      stroke="#71717a" 
      fontSize={12}
      tickLine={false}
      axisLine={false}
      tickFormatter={(v) => `$${v}`}
    />
    <Tooltip 
      contentStyle={{ 
        backgroundColor: '#111113',
        border: '1px solid #27272a',
        borderRadius: '8px',
      }}
      labelStyle={{ color: '#a1a1aa' }}
    />
    <Area
      type="monotone"
      dataKey="value"
      stroke="#22c55e"
      strokeWidth={2}
      fill="url(#profitGradient)"
    />
  </AreaChart>
</ResponsiveContainer>
```

### Bar Chart

```tsx
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

<ResponsiveContainer width="100%" height={300}>
  <BarChart data={data}>
    <XAxis dataKey="name" stroke="#71717a" fontSize={12} />
    <YAxis stroke="#71717a" fontSize={12} />
    <Bar 
      dataKey="value" 
      fill="#3b82f6" 
      radius={[4, 4, 0, 0]}
    />
  </BarChart>
</ResponsiveContainer>
```

---

## 10. Loading & Empty States

### Loading

```tsx
// Full page loading
<div className="flex items-center justify-center h-64">
  <div className="text-muted">Loading...</div>
</div>

// Skeleton for cards
<div className="animate-pulse space-y-4">
  <div className="h-4 bg-subtle rounded w-3/4" />
  <div className="h-8 bg-subtle rounded w-1/2" />
  <div className="h-4 bg-subtle rounded w-1/4" />
</div>

// Table skeleton
<div className="animate-pulse">
  {[...Array(5)].map((_, i) => (
    <div key={i} className="flex gap-4 py-3 border-b border-border-subtle">
      <div className="h-4 bg-subtle rounded w-1/3" />
      <div className="h-4 bg-subtle rounded w-1/4" />
      <div className="h-4 bg-subtle rounded w-1/6" />
    </div>
  ))}
</div>
```

### Empty State

```tsx
<div className="flex flex-col items-center justify-center py-12 text-center">
  <AlertCircle className="w-12 h-12 text-muted mb-4" />
  <h3 className="text-lg font-medium text-primary mb-1">No data found</h3>
  <p className="text-sm text-muted mb-4">
    There are no results matching your criteria.
  </p>
  <Button variant="outline">Clear filters</Button>
</div>
```

### Error State

```tsx
<div className="bg-loss-bg border border-loss/20 rounded-lg p-4">
  <div className="flex items-center gap-2 text-loss mb-2">
    <AlertCircle className="w-4 h-4" />
    <span className="font-medium">Error loading data</span>
  </div>
  <p className="text-sm text-secondary mb-3">
    {error.message}
  </p>
  <Button variant="outline" size="sm" onClick={retry}>
    Try again
  </Button>
</div>
```

---

## 11. Animation Guidelines

```tsx
// Standard transitions
className="transition-colors"        // Color changes (150ms)
className="transition-all"           // All properties (200ms)
className="transition-transform"     // Transforms (200ms)

// Hover states
className="hover:bg-elevated transition-colors"

// Loading pulse
className="animate-pulse"

// Smooth number transitions (for charts)
// Use Recharts' isAnimationActive={true}
```

**Avoid:**
- Bouncy/elastic animations
- Delays > 300ms
- Animations that block interaction
- Gratuitous motion

---

## 12. Accessibility

```tsx
// Icon buttons need labels
<Button variant="ghost" size="icon" aria-label="Refresh data">
  <RefreshCw className="w-4 h-4" />
</Button>

// Focus states (built into shadcn)
// All interactive elements have visible focus rings

// Keyboard navigation
// All buttons, links, inputs are tabbable

// Screen reader text
<span className="sr-only">Loading...</span>

// Chart accessibility
<div role="img" aria-label="PnL chart showing 24% growth over 30 days">
  <Chart />
</div>
```

---

## 13. File Naming Conventions

```
src/
├── components/
│   ├── ui/                    # shadcn + custom primitives
│   │   ├── button.tsx         # shadcn (lowercase)
│   │   ├── card.tsx           # shadcn (lowercase)
│   │   ├── pnl-value.tsx      # Custom (kebab-case)
│   │   └── stat-card.tsx      # Custom (kebab-case)
│   │
│   ├── layout/                # Layout components
│   │   ├── Header.tsx         # PascalCase
│   │   ├── Sidebar.tsx
│   │   └── Layout.tsx
│   │
│   └── reports/               # Feature-specific components
│       ├── SmartMoneyTable.tsx
│       └── ConvictionMeter.tsx
│
├── pages/                     # Route components
│   ├── Dashboard.tsx          # PascalCase
│   ├── Login.tsx
│   └── reports/
│       ├── SmartMoney.tsx
│       └── EdgeAnalysis.tsx
│
├── lib/                       # Utilities
│   ├── utils.ts               # cn() helper
│   ├── formatters.ts          # Formatting functions
│   ├── api.ts                 # API client
│   └── auth.tsx               # Auth context
│
└── types/
    └── index.ts               # TypeScript interfaces
```

---

## 14. Claude Code Instructions

When generating UI code for this project:

1. **Always use design system colors** via Tailwind classes
2. **Numbers are sacred** - Always `font-mono tabular-nums`
3. **Profit = green, Loss = red** - No exceptions
4. **Use shadcn components** when available
5. **Import from @/** - Use path aliases
6. **Follow the component patterns** in this document
7. **Keep it dense** - Resist adding whitespace
8. **Handle loading/empty/error states** for all data fetching

---

## 15. Quick Reference

### Color Classes
```
Backgrounds: bg-base, bg-surface, bg-elevated, bg-subtle
Text: text-primary, text-secondary, text-muted
Borders: border-border-subtle, border-border-default
Semantic: text-profit, text-loss, text-accent
Tints: bg-profit-bg, bg-loss-bg
```

### Common Patterns
```tsx
// Card container
className="bg-surface border border-border-subtle rounded-lg p-4"

// Table header cell
className="text-left text-xs font-medium text-muted uppercase tracking-wide py-3 px-4"

// Table data cell
className="py-3 px-4 text-sm"

// Number in table
className="font-mono tabular-nums text-right"

// Clickable row
className="hover:bg-elevated transition-colors cursor-pointer"

// Profit number
className="font-mono tabular-nums text-profit"

// Loss number
className="font-mono tabular-nums text-loss"

// Badge
className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
```

---

*Version 1.0 | Last updated: January 2025*