import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
// `base` is env-driven so the same build works at a domain root (default) or under a
// GitHub Pages project path (`/<repo>/`). The deploy workflow sets VITE_BASE accordingly.
export default defineConfig({
  base: process.env.VITE_BASE || '/',
  plugins: [react()],
})
