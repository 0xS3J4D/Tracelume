import { defineConfig } from "@playwright/test";

const executablePath = process.env.PW_CHROMIUM_PATH || undefined;

export default defineConfig({
  testDir: "e2e",
  timeout: 30_000,
  use: { baseURL: "http://127.0.0.1:5173", launchOptions: { executablePath } },
  webServer: [
    { command: "../backend/.venv/bin/python ../backend/tests/e2e_server.py 8000", url: "http://127.0.0.1:8000/api/health", reuseExistingServer: false },
    { command: "npx vite --host 127.0.0.1 --port 5173 --strictPort", url: "http://127.0.0.1:5173", reuseExistingServer: false },
  ],
});
