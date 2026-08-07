import type { Config } from 'tailwindcss'

// Paleta CRATE: consola de sampler / vinilo japonés 70s.
// Charcoal cálido, ámbar de LCD, teal jazz, y semáforo para tiers/estados.
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        crate: {
          bg: '#151007',
          panel: '#1E1710',
          panel2: '#271E14',
          ink: '#ECE2D0',
          soft: '#B6A98F',
          faint: '#877C66',
          line: '#382D1D',
          amber: '#F0B24A',      // LCD / acento
          teal: '#6FB2A6',       // jazz / secundario
          lcd: '#141009',        // fondo de pantallita
          lcdInk: '#F2B349',
          go: '#88B15A',         // sólido / saved
          warn: '#D98F3B',       // limitado / seen
          stop: '#CB6650',       // pesado / rejected
        },
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Cascadia Code', 'JetBrains Mono', 'Menlo', 'Consolas', 'monospace'],
        sans: ['system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'Helvetica', 'Arial', 'sans-serif'],
      },
      backgroundImage: {
        // grano cinematográfico sutil, aplicable como overlay
        grain: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E\")",
      },
    },
  },
  plugins: [],
} satisfies Config
