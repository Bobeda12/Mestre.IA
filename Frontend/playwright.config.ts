import { defineConfig, devices } from '@playwright/test';

// Etapa 7 — primeira suíte e2e do frontend. Sobe os dois servidores de
// verdade (front + back); só o turno de chat (`/chat/stream`) é
// interceptado via `page.route` no teste, pra não depender de rede nem de
// GROQ_API_KEY em CI — mesmo princípio de `tests/test_smoke.py` no backend
// (`narrator.client = None`), só que na borda do browser em vez do Python.
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: [
    {
      command: 'npm run dev',
      url: 'http://localhost:5173',
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
    {
      command: 'uv run --project ../Backend uvicorn app.main:app --app-dir ../Backend --port 8000',
      url: 'http://localhost:8000/options/races',
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
  ],
});
