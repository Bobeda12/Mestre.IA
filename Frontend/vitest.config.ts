import path from 'node:path'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Config separada de vite.config.ts (Etapa 7) — mesmo alias `@` (shadcn/ui),
// mas sem o plugin do Tailwind: os testes não renderizam CSS de verdade,
// só a árvore de componentes (jsdom), então processar o Tailwind aqui só
// deixaria a suíte mais lenta à toa.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
    css: false,
    // `e2e/` é a suíte do Playwright (webServer real, config própria) —
    // sem isso o Vitest tenta importar `@playwright/test` dentro do jsdom
    // e quebra com "test() did not expect to be called here".
    exclude: ['e2e/**', 'node_modules/**'],
  },
})
