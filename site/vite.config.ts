import { defineConfig } from 'vite'

export default defineConfig({
  base: process.env.BASE_PATH ?? '/Analyzing-Stock-Performance-and-Building-a-Dashboard/',
  build: { target: 'es2022', chunkSizeWarningLimit: 2500 },
})
