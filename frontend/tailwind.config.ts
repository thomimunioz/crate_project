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
          faint: '#9A8E75',      // subido de #877C66: ahora pasa AA sobre panel
          line: '#382D1D',
          amber: '#F0B24A',      // LCD / acento
          teal: '#6FB2A6',       // jazz / secundario
          lcd: '#141009',        // fondo de pantallita
          lcdInk: '#F2B349',
          go: '#88B15A',         // sólido / saved
          warn: '#D98F3B',       // limitado / seen
          stop: '#CB6650',       // pesado / rejected

          // --- ficha de cartón (el ResultCard) ---
          card: '#221A11',       // cartón, un punto más claro que panel
          cardEdge: '#2C2216',   // canto gastado de la ficha
          dust: '#5E543F',       // polvo: líneas, bordes decorativos, timestamps
          amberDim: '#7A5A22',   // ámbar apagado, para trazos que no deben gritar
        },
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Cascadia Code', 'JetBrains Mono', 'Menlo', 'Consolas', 'monospace'],
        sans: ['system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'Helvetica', 'Arial', 'sans-serif'],
        // serif de liner notes: solo para el wordmark y títulos de sección, nunca para datos
        display: ['Optima', 'Palatino Linotype', 'Palatino', 'Georgia', 'Times New Roman', 'serif'],
      },
      backgroundImage: {
        // grano cinematográfico sutil, aplicable como overlay
        grain: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E\")",
        // grano más marcado para el overlay fijo de toda la app
        grainHeavy: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='3'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.09'/%3E%3C/svg%3E\")",
        // fibra de cartón: rayado diagonal casi imperceptible bajo las fichas
        fibers:
          'repeating-linear-gradient(115deg, rgba(255,238,205,0.022) 0 1px, transparent 1px 6px)',
        // líneas de barrido de la pantallita
        scanlines:
          'repeating-linear-gradient(to bottom, rgba(0,0,0,0.34) 0 1px, transparent 1px 3px)',
        // viñeta cálida: la luz cae al centro, como una foto de los 70
        vignette:
          'radial-gradient(120% 85% at 50% 0%, rgba(240,178,74,0.07) 0%, transparent 55%), radial-gradient(100% 100% at 50% 100%, rgba(0,0,0,0.55) 0%, transparent 60%)',
      },
      boxShadow: {
        ficha:
          '0 1px 0 rgba(255,238,205,0.045) inset, 0 14px 28px -18px rgba(0,0,0,0.95), 0 2px 6px -4px rgba(0,0,0,0.8)',
        sticker: '0 2px 5px -1px rgba(0,0,0,0.65), 0 0 0 1px rgba(0,0,0,0.35)',
        lcdInset:
          'inset 0 0 26px rgba(0,0,0,0.8), inset 0 1px 0 rgba(242,179,73,0.14), 0 0 0 1px rgba(240,178,74,0.22)',
        glow: '0 0 14px rgba(240,178,74,0.28)',
      },
      keyframes: {
        // la ficha se revela: sale del polvo cuando el cruce la identifica
        reveal: {
          '0%': { opacity: '0', filter: 'blur(5px) saturate(0.35)', transform: 'translateY(3px)' },
          '100%': { opacity: '1', filter: 'blur(0) saturate(1)', transform: 'translateY(0)' },
        },
        // barrido del cabezal mientras se cruza contra catálogo
        scan: {
          '0%': { transform: 'translateX(-110%)' },
          '100%': { transform: 'translateX(210%)' },
        },
        // brillo que recorre los huecos del esqueleto (polvo levantándose)
        shimmer: {
          '0%': { backgroundPosition: '-160% 0' },
          '100%': { backgroundPosition: '260% 0' },
        },
        // el LCD respira, como un display viejo
        flicker: {
          '0%, 100%': { opacity: '1' },
          '48%': { opacity: '0.86' },
          '52%': { opacity: '1' },
        },
        // el sello cae sobre la ficha
        stamp: {
          '0%': { opacity: '0', transform: 'rotate(-14deg) scale(1.7)' },
          '65%': { opacity: '1', transform: 'rotate(-6deg) scale(0.96)' },
          '100%': { opacity: '1', transform: 'rotate(-6deg) scale(1)' },
        },
        spinSlow: {
          '0%': { transform: 'rotate(0deg)' },
          '100%': { transform: 'rotate(360deg)' },
        },
      },
      animation: {
        reveal: 'reveal 620ms cubic-bezier(0.2, 0.7, 0.3, 1) both',
        scan: 'scan 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        shimmer: 'shimmer 2.1s linear infinite',
        flicker: 'flicker 4.5s ease-in-out infinite',
        stamp: 'stamp 320ms cubic-bezier(0.2, 1.4, 0.4, 1) both',
        'spin-slow': 'spinSlow 8s linear infinite',
      },
    },
  },
  plugins: [],
} satisfies Config
