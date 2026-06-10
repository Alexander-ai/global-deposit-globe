import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
// `base` is env-driven so the same build works at a domain root (default) or under a
// GitHub Pages project path (`/<repo>/`). The deploy workflow sets VITE_BASE accordingly.
export default defineConfig({
  base: process.env.VITE_BASE || '/',
  plugins: [react()],
  // Honor a PORT from the environment (e.g. preview tooling) but keep Vite's default (5173)
  // for plain `npm run dev`.
  server: process.env.PORT ? { port: Number(process.env.PORT) } : undefined,
})
