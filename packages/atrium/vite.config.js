import { defineConfig } from 'vite';
import solid from 'vite-plugin-solid';

// Vite config for Atrium frontend.
// - Rendered inside Tauri WebView (production) or browser (dev).
// - Default dev server port 1420 (Tauri convention).
// - clearScreen: false so we see Tauri's CLI output too.
//
// См. docs/atrium/PLAN.md §4.1 — Tauri 2 + Vite + Solid.js.

export default defineConfig({
  plugins: [solid()],
  base: '/atrium/',
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    host: 'localhost',
  },
  envPrefix: ['VITE_', 'ATRIUM_'],
  build: {
    target: 'esnext',
    minify: 'esbuild',
    sourcemap: true,
  },
});
