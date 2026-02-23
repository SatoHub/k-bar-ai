import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30000,
  expect: { timeout: 10000 },
  fullyParallel: false,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: process.env.BASE_URL || "http://133.117.72.213",
    ...(process.env.BASE_URL
      ? {}
      : {
          httpCredentials: {
            username: "admin",
            password: "kbar2026ai",
          },
        }),
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "PC",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "SP",
      use: {
        ...devices["iPhone 14"],
        defaultBrowserType: "chromium",
      },
    },
  ],
});
