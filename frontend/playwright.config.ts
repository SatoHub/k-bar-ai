import { defineConfig, devices } from "@playwright/test";
import { readFileSync } from "node:fs";

// Load credentials from a gitignored .env.local so secrets never live in source.
// Format: KEY=value per line. Existing shell env vars take precedence.
try {
  const text = readFileSync(".env.local", "utf8");
  for (const line of text.split("\n")) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m && process.env[m[1]] === undefined) {
      process.env[m[1]] = m[2].replace(/^["']|["']$/g, "");
    }
  }
} catch {
  // No .env.local present — rely on shell env (or localhost defaults below).
}

const baseURL = process.env.HEALTHCHECK_URL || "http://localhost:3000";
const authUser = process.env.HEALTHCHECK_USER;
const authPass = process.env.HEALTHCHECK_PASS;

export default defineConfig({
  testDir: "./e2e",
  timeout: 30000,
  expect: { timeout: 10000 },
  fullyParallel: false,
  retries: 0,
  reporter: "list",
  use: {
    baseURL,
    ...(authUser && authPass
      ? { httpCredentials: { username: authUser, password: authPass } }
      : {}),
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
