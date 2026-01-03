/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Backgrounds
        base: "hsl(var(--bg-base))",
        surface: "hsl(var(--bg-surface))",
        elevated: "hsl(var(--bg-elevated))",
        subtle: "hsl(var(--bg-subtle))",
        
        // Text
        primary: "hsl(var(--text-primary))",
        secondary: "hsl(var(--text-secondary))",
        muted: "hsl(var(--text-muted))",
        
        // Borders
        "border-subtle": "hsl(var(--border-subtle))",
        "border-default": "hsl(var(--border-default))",
        
        // Semantic
        profit: "hsl(var(--profit))",
        "profit-bg": "hsl(var(--profit-bg))",
        loss: "hsl(var(--loss))",
        "loss-bg": "hsl(var(--loss-bg))",
        accent: "hsl(var(--accent))",
        "accent-hover": "hsl(var(--accent-hover))",
        warning: "hsl(var(--warning))",
        info: "hsl(var(--info))",
        
        // shadcn compatibility
        background: "hsl(var(--bg-base))",
        foreground: "hsl(var(--text-primary))",
        card: {
          DEFAULT: "hsl(var(--bg-surface))",
          foreground: "hsl(var(--text-primary))",
        },
        popover: {
          DEFAULT: "hsl(var(--bg-surface))",
          foreground: "hsl(var(--text-primary))",
        },
        muted: {
          DEFAULT: "hsl(var(--bg-subtle))",
          foreground: "hsl(var(--text-muted))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--text-primary))",
        },
        destructive: {
          DEFAULT: "hsl(var(--loss))",
          foreground: "hsl(var(--text-primary))",
        },
        border: "hsl(var(--border-subtle))",
        input: "hsl(var(--border-default))",
        ring: "hsl(var(--accent))",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "SF Mono", "Consolas", "monospace"],
      },
      borderRadius: {
        lg: "8px",
        md: "6px",
        sm: "4px",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}