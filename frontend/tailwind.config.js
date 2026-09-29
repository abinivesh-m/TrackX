/** @type {import('tailwindcss').Config} */
//
// TrackX operations-console palette.
//
// Deliberately NOT the generic hackathon-AI-dashboard look: no blue->purple
// gradient family, no neon glassmorphism accent. This is modeled on
// traffic-signal semantics and control-room/NOC monitoring UIs (signal
// amber for attention/primary actions, a cool telemetry cyan for
// live/active data, and standard red/amber/green for alert severity - the
// same vocabulary a traffic engineer already reads on the street).
//
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Graphite base - flat, no gradient mesh. This is the console shell.
        graphite: {
          950: '#08090b',
          900: '#0d0f13',
          850: '#12151a',
          800: '#171a21',
          750: '#1c202a',
          700: '#232733',
          600: '#333947',
          500: '#4a5163',
          400: '#6b7385',
        },
        // Signal amber - the ONE brand accent. Used for primary actions,
        // active nav state, focus rings, and "attention" map elements.
        // Pulled from actual traffic-signal / hazard-beacon amber, not a
        // UI-kit "warning" yellow.
        signal: {
          300: '#f7c463',
          400: '#f3b53e',
          500: '#ec9d1e',
          600: '#c97f13',
          700: '#9c6110',
        },
        // Telemetry cyan - secondary accent reserved for live/active data:
        // camera-online indicators, live trajectory lines, real-time feed
        // markers. Never used decoratively.
        telemetry: {
          300: '#7fe3e8',
          400: '#42c9d1',
          500: '#22a7b0',
          600: '#187e85',
        },
        // Traffic-light severity vocabulary for alerts/status - intentionally
        // desaturated versions of the literal traffic-light colors rather than
        // generic Tailwind red/green/amber, so they read as "operational
        // status" rather than "UI kit badge".
        clear: {
          400: '#5fb87a',
          500: '#3f9e5c',
          600: '#2f7d47',
        },
        caution: {
          400: '#e8ab3d',
          500: '#cf8f22',
          600: '#a8721a',
        },
        critical: {
          400: '#e2645a',
          500: '#c8473d',
          600: '#9f362e',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        // Data face - plate numbers, camera IDs, lat/lon, timestamps, speeds.
        // No ligatures: a misread character in a plate number is a real-world
        // error, not a cosmetic one.
        mono: ['"JetBrains Mono"', '"IBM Plex Mono"', 'monospace'],
      },
      borderRadius: {
        // Sharp, drafting-table corners instead of the 16-24px "bubble card"
        // radius generic dashboards default to.
        sm: '2px',
        DEFAULT: '3px',
        md: '4px',
      },
      animation: {
        'live-blink': 'live-blink 1.8s ease-in-out infinite',
        'scan': 'scan 2.4s linear infinite',
      },
      keyframes: {
        // Functional only: a genuine "this feed is live" indicator, the same
        // pattern a CCTV/broadcast monitor uses - not a decorative pulse on
        // every icon on the page.
        'live-blink': {
          '0%, 100%': { opacity: 1 },
          '50%': { opacity: 0.35 },
        },
        'scan': {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100%)' },
        },
      },
    },
  },
  plugins: [],
}
