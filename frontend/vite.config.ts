import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // SIH26127 live-stream/webcam-stream fix: the real WebSocket
        // endpoints this app uses (/api/v1/observations/live-stream/{id}
        // and /api/v1/observations/webcam-stream/{id}) live under /api,
        // not under the separate /ws proxy entry below. Without ws:true
        // here, Vite's dev-server proxy only forwards this prefix's plain
        // HTTP requests - a WebSocket upgrade to a /api/... path would
        // fail to connect at all in `npm run dev` (it would still work in
        // a production build, where the backend serves the frontend from
        // the same origin/port and no proxy is involved) - so this was a
        // real dev-mode gap, not a hypothetical one.
        ws: true
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true
      },
      // SIH26127 fix (2026-09-14): the annotated-frame and plate-crop images
      // the backend generates (backend/app/main.py mounts them at
      // /media/annotated, /media/plate-crops, /media/annotated-videos) were
      // never reachable in `npm run dev` - only /api and /ws were proxied
      // here, so a browser request to /media/... hit Vite's own dev server
      // instead of the backend on :8000, got nothing real back, and every
      // <img src={obs.annotated_url}>/<img src={obs.plate_crop_url}> in
      // VideoDemoPage.tsx/CameraLivePage.tsx rendered as a broken image -
      // even though the backend had already generated a real, correct file
      // and returned a correct URL for it. Same class of gap as the /api
      // ws:true fix above, just for static media instead of WebSockets.
      // (In a production build this is a non-issue - the backend serves the
      // frontend itself, same origin, no proxy involved.)
      '/media': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: true
  }
})
