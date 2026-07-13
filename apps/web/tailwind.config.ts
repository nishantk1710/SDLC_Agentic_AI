import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: '#2563EB',
        'primary-hover': '#225BD8',
        error: '#C0392B',
        'error-hover': '#B13428',
        text: '#1A1A1A',
        'text-secondary': '#6B7280',
        surface: '#FFFFFF',
        'surface-alt': '#F9FAFB',
        border: '#E5E7EB',
        success: '#16A34A',
        warning: '#D97706',
        'disabled-bg': '#E5E7EB',
        'disabled-text': '#9CA3AF',
        'focus-ring': '#93C5FD',
        'on-primary': '#FFFFFF',
      },
      spacing: {
        sm: '8px',
        md: '16px',
        lg: '24px',
      },
      borderRadius: {
        md: '8px',
        pill: '999px',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', '"Segoe UI"', 'sans-serif'],
      },
      fontSize: {
        body: ['16px', '24px'],
        h1: ['28px', '34px'],
        h2: ['22px', '28px'],
        h3: ['18px', '24px'],
        small: ['14px', '20px'],
      },
      screens: {
        sm: '375px',
        md: '376px',
        lg: '1024px',
      },
      boxShadow: {
        card: '0 1px 3px rgba(26, 26, 26, 0.08)',
        modal: '0 8px 24px rgba(26, 26, 26, 0.16)',
      },
      keyframes: {
        spin: {
          to: { transform: 'rotate(360deg)' },
        },
        'modal-in': {
          from: { opacity: '0', transform: 'translateY(16px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        spin: 'spin 800ms linear infinite',
        'modal-in': 'modal-in 200ms ease-out',
      },
    },
  },
  plugins: [],
} satisfies Config
