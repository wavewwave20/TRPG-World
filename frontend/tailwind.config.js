/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6', // Brand Blue
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
        },
        slate: {
          50: '#f8fafc', // Main Background
          100: '#f1f5f9', // Panel Background
          200: '#e2e8f0', // Borders
          300: '#cbd5e1',
          400: '#94a3b8', // Muted Text
          500: '#64748b',
          600: '#475569',
          700: '#334155', // Body Text
          800: '#1e293b', // Headings
          900: '#0f172a',
        },
        accent: {
          gold: '#f59e0b', // Success/Highlight
          red: '#ef4444', // Danger
          green: '#10b981', // Success
        }
      },
      fontFamily: {
        heading: ['"Inter"', 'sans-serif'],
        sans: ['"Inter"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      boxShadow: {
        'soft': '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
        'card': '0 0 0 1px rgba(0,0,0,0.05), 0 2px 4px rgba(0,0,0,0.1)',
        'card-hover': '0 0 0 1px rgba(59,130,246,0.1), 0 4px 12px rgba(59,130,246,0.1)',
        'modal': '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        fadeOut: {
          '0%': { opacity: '1' },
          '100%': { opacity: '0' },
        },
        scaleIn: {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        scaleOut: {
          '0%': { opacity: '1', transform: 'scale(1)' },
          '100%': { opacity: '0', transform: 'scale(0.95)' },
        },
        slideInRight: {
          '0%': { opacity: '0', transform: 'translateX(20px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        slideOutLeft: {
          '0%': { opacity: '1', transform: 'translateX(0)' },
          '100%': { opacity: '0', transform: 'translateX(-20px)' },
        },
        slideInLeft: {
          '0%': { opacity: '0', transform: 'translateX(-20px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        slideOutRight: {
          '0%': { opacity: '1', transform: 'translateX(0)' },
          '100%': { opacity: '0', transform: 'translateX(20px)' },
        },
      },
      animation: {
        fadeIn: 'fadeIn 0.2s ease-out',
        fadeOut: 'fadeOut 0.2s ease-in',
        scaleIn: 'scaleIn 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
        scaleOut: 'scaleOut 0.2s cubic-bezier(0.4, 0, 1, 1)',
        slideInRight: 'slideInRight 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
        slideOutLeft: 'slideOutLeft 0.3s cubic-bezier(0.4, 0, 1, 1)',
        slideInLeft: 'slideInLeft 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
        slideOutRight: 'slideOutRight 0.3s cubic-bezier(0.4, 0, 1, 1)',
      },
    },
  },
  plugins: [],
}
