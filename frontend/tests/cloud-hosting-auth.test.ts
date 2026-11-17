import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe("Cognito on a second hosting origin", () => {
  it("keeps password auth and suppresses hosted redirects until the origin is registered", async () => {
    vi.stubEnv("NEXT_PUBLIC_COGNITO_CLIENT_ID", "existing-client");
    vi.stubEnv("NEXT_PUBLIC_COGNITO_USER_POOL_ID", "us-east-1_existing");
    vi.stubEnv(
      "NEXT_PUBLIC_COGNITO_DOMAIN",
      "existing.auth.us-east-1.amazoncognito.com",
    );
    vi.stubEnv("NEXT_PUBLIC_COGNITO_GOOGLE_ENABLED", "true");
    vi.stubEnv("NEXT_PUBLIC_COGNITO_HOSTED_REDIRECTS_ENABLED", "false");
    vi.resetModules();

    const settings = await import("@/lib/auth-config");
    const { hostedLogoutUrl } = await import("@/lib/auth");
    expect(settings.authConfigured).toBe(true);
    expect(settings.config.clientId).toBe("existing-client");
    expect(settings.hostedSignInConfigured).toBe(false);
    expect(settings.googleEnabled).toBe(false);
    expect(hostedLogoutUrl()).toBeNull();
  });

  it("preserves hosted sign-in and logout for existing builds by default", async () => {
    vi.stubEnv("NEXT_PUBLIC_COGNITO_CLIENT_ID", "existing-client");
    vi.stubEnv("NEXT_PUBLIC_COGNITO_USER_POOL_ID", "us-east-1_existing");
    vi.stubEnv(
      "NEXT_PUBLIC_COGNITO_DOMAIN",
      "existing.auth.us-east-1.amazoncognito.com",
    );
    vi.stubEnv("NEXT_PUBLIC_COGNITO_GOOGLE_ENABLED", "true");
    vi.stubEnv("NEXT_PUBLIC_COGNITO_HOSTED_REDIRECTS_ENABLED", "");
    vi.resetModules();

    const settings = await import("@/lib/auth-config");
    const { hostedLogoutUrl } = await import("@/lib/auth");
    expect(settings.hostedSignInConfigured).toBe(true);
    expect(settings.googleEnabled).toBe(true);
    expect(new URL(hostedLogoutUrl()!).hostname).toBe(settings.config.domain);
  });
});
