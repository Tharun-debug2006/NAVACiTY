/**
 * Tailwind configuration.
 *
 * The colours below mirror the design tokens in `src/styles/tokens.css`; the
 * CSS file is the single source of truth, this file only exposes the same
 * values as Tailwind utilities so that the JSX stays readable.
 *
 * @type {import('tailwindcss').Config}
 */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Brand / metro family (indigo).
        metro: {
          50: '#eef2ff',
          100: '#e0e7ff',
          200: '#c7d2fe',
          600: '#4f46e5',
          700: '#1d3fbf',
          800: '#1e3a8a',
        },
        // Bus family (amber).
        bus: {
          50: '#fffbeb',
          100: '#fef3c7',
          200: '#fde68a',
          600: '#b7791f',
          700: '#92400e',
        },
        // Crowd levels.  Always used together with a text label.
        crowd: {
          low: '#0f8a5f',
          'low-soft': '#ecfdf5',
          moderate: '#0369a1',
          'moderate-soft': '#f0f9ff',
          high: '#c2410c',
          'high-soft': '#fff7ed',
          critical: '#b91c1c',
          'critical-soft': '#fef2f2',
        },
      },
      fontFamily: {
        sans: [
          'ui-sans-serif',
          'system-ui',
          'Segoe UI',
          'Roboto',
          'Noto Sans',
          'Noto Sans Devanagari',
          'Noto Sans Kannada',
          'sans-serif',
        ],
      },
      maxWidth: {
        content: '1152px',
      },
      borderRadius: {
        card: '12px',
        control: '8px',
      },
      keyframes: {
        'fade-in': {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 0.2s ease-out',
      },
    },
  },
  plugins: [],
}
