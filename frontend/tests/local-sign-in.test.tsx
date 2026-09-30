import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { LocalSignInForm } from "@/components/local-sign-in";
import { getIdToken, getSession } from "@/lib/auth";
import { makeIdToken } from "./utils";

function apiReplies(status: number, body: unknown) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: status < 400,
    status,
    json: async () => body,
  } as Response);
}

describe("local sign-in", () => {
  it("is what a build without a pool offers", async () => {
    vi.stubEnv("NEXT_PUBLIC_COGNITO_CLIENT_ID", "");
    vi.resetModules();
    const auth = await import("@/lib/auth");
    expect(auth.authConfigured).toBe(false);
    expect(auth.googleEnabled).toBe(false);
    vi.unstubAllEnvs();
  });

  it("gets a token from the API and stores the session", async () => {
    const spy = apiReplies(200, {
      id_token: makeIdToken({ email: "alice@example.com", name: "Alice" }),
    });
    render(<LocalSignInForm />);

    await userEvent.type(screen.getByLabelText("Email"), "alice@example.com");
    await userEvent.type(screen.getByLabelText(/Name/), "Alice");
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() => expect(getSession()?.name).toBe("Alice"));
    const [url, init] = spy.mock.calls[0];
    expect(url).toBe("http://localhost:8000/local/sign-in");
    expect(JSON.parse(String(init?.body))).toEqual({
      email: "alice@example.com",
      name: "Alice",
    });
  });

  it("says so when the API does not offer local sign-in", async () => {
    apiReplies(404, { detail: "Not Found" });
    render(<LocalSignInForm />);

    await userEvent.type(screen.getByLabelText("Email"), "alice@example.com");
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "APP_ENV=development",
    );
    expect(getSession()).toBeNull();
  });

  it("signs out when a token with nothing to renew it runs out", async () => {
    window.localStorage.setItem(
      "peach.session",
      JSON.stringify({
        idToken: makeIdToken(),
        refreshToken: "",
        expiresAt: Date.now() + 30_000,
      }),
    );
    const spy = vi.spyOn(globalThis, "fetch");
    await expect(getIdToken()).resolves.toBeNull();
    expect(getSession()).toBeNull();
    expect(spy).not.toHaveBeenCalled();
  });
});
