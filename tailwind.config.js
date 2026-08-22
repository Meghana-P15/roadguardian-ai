/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#0b0e14',
        card: '#161b22',
        cardHover: '#1c2128',
        cardSelected: '#21262d',
        border: '#30363d',
        critical: '#ff334b',
        high: '#ff9f1c',
        medium: '#ffe600',
        low: '#2ec4b6'
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif']
      }
    },
  },
  plugins: [],
}
