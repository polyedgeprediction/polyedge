# PolyMarket Analytics - Frontend Design System

Everything you need to build a professional trading dashboard with Django + Vite + React.

---

## 📁 Files in This Package

| File | Purpose |
|------|---------|
| **DESIGN_SYSTEM.md** | Source of truth - colors, typography, spacing, component specs |
| **COMPONENTS.md** | Ready-to-copy component code |
| **PROMPTS.md** | Copy-paste prompts for Claude Code |

---

## 🚀 Quick Start

### 1. Set Up the Project

Follow `SETUP.md` to:
- Create Vite project
- Install dependencies
- Configure Tailwind
- Initialize shadcn/ui
- Set up Django integration

### 2. Copy Base Components

From `COMPONENTS.md`, copy these files into your project:
- `src/lib/utils.ts`
- `src/lib/formatters.ts`
- `src/lib/api.ts`
- `src/lib/auth.tsx`
- All components in `src/components/`

### 3. Start Building

Use prompts from `PROMPTS.md` to generate new components and pages consistently.

---

## 🎯 The Core Principle

**Consistency comes from constraints.**

Every file in this package enforces the same rules:
- Same colors (dark theme, profit=green, loss=red)
- Same typography (Inter for text, JetBrains Mono for numbers)
- Same spacing (Tailwind's scale)
- Same patterns (Card, StatCard, DataTable)

When you (or Claude Code) generate new UI, reference `DESIGN_SYSTEM.md` to ensure it matches.

---

## 🔧 Tech Stack

```
Django (Backend)
    ├── REST API (/api/*)
    ├── Authentication (sessions, cookies)
    └── Serves frontend in production

Vite + React (Frontend)
    ├── React 18 with TypeScript
    ├── Tailwind CSS (styling)
    ├── shadcn/ui (component primitives)
    ├── React Router (routing)
    ├── Lucide React (icons)
    └── Recharts (charts)
```

---

## 📋 Design Rules at a Glance

### Colors
```
Backgrounds: bg-base → bg-surface → bg-elevated → bg-subtle
Text: text-primary → text-secondary → text-muted
Semantic: text-profit (green), text-loss (red), text-accent (blue)
```

### Numbers
```tsx
// ALL numbers must use this:
className="font-mono tabular-nums"

// PnL specifically:
className="font-mono tabular-nums text-profit"  // positive
className="font-mono tabular-nums text-loss"    // negative
```

### Tables
```tsx
// Header
className="text-xs font-medium text-muted uppercase tracking-wide"

// Number cells
className="text-right font-mono tabular-nums"

// Row hover
className="hover:bg-elevated transition-colors"
```

---

## 🔄 Development Workflow

```bash
# Terminal 1: Django
cd backend
python manage.py runserver  # :8000

# Terminal 2: Vite
cd frontend
npm run dev  # :5173

# Visit http://localhost:5173
# Vite proxies /api/* to Django
```

---

## 📦 Production Build

```bash
# Build frontend
cd frontend
npm run build  # → outputs to backend/static/dist/

# Run Django only
cd backend
python manage.py collectstatic
python manage.py runserver  # :8000

# Django serves everything
```

---

## ✅ Quality Checklist

Before shipping any page:

- [ ] All colors use design tokens (no hardcoded hex)
- [ ] Numbers are `font-mono tabular-nums`
- [ ] PnL shows correct colors (+green, -red)
- [ ] Tables have proper alignment
- [ ] Loading state looks good
- [ ] Error state is handled
- [ ] Empty state is handled
- [ ] Responsive on tablet (768px+)

---

## 📚 Reference Links

- [Tailwind CSS](https://tailwindcss.com/docs)
- [shadcn/ui](https://ui.shadcn.com/)
- [Lucide Icons](https://lucide.dev/icons/)
- [Recharts](https://recharts.org/)
- [React Router](https://reactrouter.com/)

---

*Built for speed and consistency. Start simple, ship fast, iterate.*