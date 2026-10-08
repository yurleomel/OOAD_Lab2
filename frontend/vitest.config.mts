import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": import.meta.dirname },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
    // A pretend pool, so lib/auth is configured; Cognito itself is mocked per test.
    env: {
      NEXT_PUBLIC_COGNITO_REGION: "us-east-1",
      NEXT_PUBLIC_COGNITO_USER_POOL_ID: "us-east-1_test",
      NEXT_PUBLIC_COGNITO_CLIENT_ID: "test-client",
      NEXT_PUBLIC_COGNITO_DOMAIN: "peach-test.auth.us-east-1.amazoncognito.com",
      NEXT_PUBLIC_COGNITO_GOOGLE_ENABLED: "true",
    },
  },
});
