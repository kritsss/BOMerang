import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 120_000,
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:5173",
    viewport: { width: 1360, height: 900 },
    launchOptions: process.env.PW_CHROMIUM_PATH ? { executablePath: process.env.PW_CHROMIUM_PATH } : {},
    acceptDownloads: true,
  },
});
