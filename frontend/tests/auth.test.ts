import { createHash } from "node:crypto";

import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  completeHostedSignIn,
  getIdToken,
  getSession,
  hostedLogoutUrl,
  signIn,
  signOut,
  signUp,
  startGoogleSignIn,
  startHostedSignIn,
  useSession,
} from "@/lib/auth";
import { makeIdToken, signInAs } from "./utils";

type Reply = { status?: number; body: unknown };

/** Queues Cognito's answers, in order, and returns the fetch spy. */
function cognitoReplies(...replies: Reply[]) {
  const spy = vi.spyOn(globalThis, "fetch");
  for (const { status = 200, body } of replies) {
    spy.mockResolvedValueOnce({
      ok: status < 400,
      status,
      json: async () => body,
    } as Response);
  }
  return spy;
}

function sent(spy: ReturnType<typeof cognitoReplies>, call = 0) {
  const init = spy.mock.calls[call][1] as RequestInit;
  const headers = init.headers as Record<string, string>;
  return {
    target: headers["X-Amz-Target"],
    body: JSON.parse(String(init.body)),
  };
}

function storeExpiring(idToken = makeIdToken()) {
  window.localStorage.setItem(
    "peach.session",
    JSON.stringify({
      idToken,
      refreshToken: "refresh-token",
      expiresAt: Date.now() + 30_000,
    }),
  );
}

describe("email and password", () => {
  it("signs in with the password flow and exposes the session", async () => {
    const spy = cognitoReplies({
      body: {
        AuthenticationResult: {
          IdToken: makeIdToken({ name: "Олена Коваль" }),
          RefreshToken: "r1",
          ExpiresIn: 3600,
        },
      },
    });

    await signIn("alice@example.com", "correct horse 1");

    expect(sent(spy)).toEqual({
      target: "AWSCognitoIdentityProviderService.InitiateAuth",
      body: {
        AuthFlow: "USER_PASSWORD_AUTH",
        ClientId: "test-client",
        AuthParameters: {
          USERNAME: "alice@example.com",
          PASSWORD: "correct horse 1",
        },
      },
    });
    // Non-ASCII names survive the base64url round trip.
    expect(getSession()).toEqual({
      sub: "alice-sub",
      email: "alice@example.com",
      name: "Олена Коваль",
    });
  });

  it("turns Cognito errors into readable ones", async () => {
    cognitoReplies({
      status: 400,
      body: {
        __type: "NotAuthorizedException",
        message: "Incorrect username or password.",
      },
    });
    await expect(signIn("alice@example.com", "wrong")).rejects.toMatchObject({
      code: "NotAuthorizedException",
      message: "Incorrect email or password.",
    });
    expect(getSession()).toBeNull();
  });

  it("reads namespaced error types too", async () => {
    cognitoReplies({
      status: 400,
      body: { __type: "com.amazonaws.cognito#UsernameExistsException" },
    });
    await expect(
      signUp({
        name: "Alice",
        email: "alice@example.com",
        password: "pass1234",
      }),
    ).rejects.toMatchObject({ code: "UsernameExistsException" });
  });

  it("sends name and email as attributes on sign-up", async () => {
    const spy = cognitoReplies({ body: { UserConfirmed: false } });
    await expect(
      signUp({
        name: "Alice",
        email: "alice@example.com",
        password: "pass1234",
      }),
    ).resolves.toEqual({ confirmed: false });
    expect(sent(spy).body.UserAttributes).toEqual([
      { Name: "email", Value: "alice@example.com" },
      { Name: "name", Value: "Alice" },
    ]);
  });

  it("follows sign-in and sign-out in useSession", async () => {
    const { result } = renderHook(() => useSession());
    expect(result.current).toBeNull();

    cognitoReplies({
      body: {
        AuthenticationResult: {
          IdToken: makeIdToken(),
          RefreshToken: "r1",
          ExpiresIn: 3600,
        },
      },
    });
    await act(() => signIn("alice@example.com", "pw"));
    expect(result.current?.email).toBe("alice@example.com");

    act(() => signOut());
    expect(result.current).toBeNull();
  });
});

describe("tokens for the API", () => {
  it("hands out a fresh token without calling Cognito", async () => {
    const token = signInAs();
    const spy = vi.spyOn(globalThis, "fetch");
    await expect(getIdToken()).resolves.toBe(token);
    expect(spy).not.toHaveBeenCalled();
  });

  it("is null when signed out", async () => {
    await expect(getIdToken()).resolves.toBeNull();
  });

  it("refreshes a token about to expire, once for concurrent callers", async () => {
    storeExpiring();
    const renewed = makeIdToken({ email: "alice@example.com", iat: 2 });
    const spy = cognitoReplies({
      body: { AuthenticationResult: { IdToken: renewed, ExpiresIn: 3600 } },
    });

    const tokens = await Promise.all([getIdToken(), getIdToken()]);

    expect(tokens).toEqual([renewed, renewed]);
    expect(spy).toHaveBeenCalledTimes(1);
    expect(sent(spy).body).toMatchObject({
      AuthFlow: "REFRESH_TOKEN_AUTH",
      AuthParameters: { REFRESH_TOKEN: "refresh-token" },
    });
    // No rotation: the refresh token is kept for next time.
    const stored = JSON.parse(window.localStorage.getItem("peach.session")!);
    expect(stored.refreshToken).toBe("refresh-token");
  });

  it("signs out when the pool refuses the refresh", async () => {
    storeExpiring();
    cognitoReplies({
      status: 400,
      body: {
        __type: "NotAuthorizedException",
        message: "Refresh Token has expired",
      },
    });
    await expect(getIdToken()).resolves.toBeNull();
    expect(getSession()).toBeNull();
  });

  it("keeps the session when Cognito is unreachable", async () => {
    storeExpiring();
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("offline"));
    await expect(getIdToken()).resolves.toBeNull();
    expect(getSession()).not.toBeNull();
  });
});

describe("the hosted domain, through oidc-client-ts", () => {
  /** Captures where the library sends the browser instead of navigating. */
  function captureRedirect() {
    const assign = vi.fn();
    vi.spyOn(window, "location", "get").mockReturnValue({
      ...window.location,
      assign,
    });
    // signinRedirect never settles - the page is leaving - so wait for the redirect.
    return async () => {
      await vi.waitFor(() => expect(assign).toHaveBeenCalled());
      return new URL(assign.mock.calls[0][0]);
    };
  }

  /** The PKCE verifier oidc-client-ts saved for this state. */
  function savedVerifier(state: string): string {
    return JSON.parse(window.localStorage.getItem(`oidc.${state}`)!)
      .code_verifier;
  }

  it("starts Google sign-in with a PKCE challenge it can check later", async () => {
    const redirectedTo = captureRedirect();
    void startGoogleSignIn();
    const url = await redirectedTo();
    const state = url.searchParams.get("state")!;

    expect(url.origin).toBe(
      "https://peach-test.auth.us-east-1.amazoncognito.com",
    );
    expect(url.pathname).toBe("/oauth2/authorize");
    expect(Object.fromEntries(url.searchParams)).toMatchObject({
      identity_provider: "Google",
      response_type: "code",
      client_id: "test-client",
      scope: "openid email profile",
      code_challenge_method: "S256",
      code_challenge: createHash("sha256")
        .update(savedVerifier(state))
        .digest("base64url"),
    });
    expect(url.searchParams.get("redirect_uri")).toMatch(/\/auth\/callback$/);
  });

  it("opens the managed login page when no provider is named", async () => {
    const redirectedTo = captureRedirect();
    void startHostedSignIn();
    const url = await redirectedTo();

    expect(url.pathname).toBe("/oauth2/authorize");
    expect(url.searchParams.has("identity_provider")).toBe(false);
  });

  it("logs out of the hosted domain back to the site root", () => {
    const url = new URL(hostedLogoutUrl()!);

    expect(url.origin + url.pathname).toBe(
      "https://peach-test.auth.us-east-1.amazoncognito.com/logout",
    );
    expect(Object.fromEntries(url.searchParams)).toEqual({
      client_id: "test-client",
      logout_uri: `${window.location.origin}/`,
    });
  });

  it("refuses a callback for a sign-in it did not start", async () => {
    const spy = vi.spyOn(globalThis, "fetch");
    await expect(
      completeHostedSignIn(
        `${window.location.origin}/auth/callback?code=c&state=theirs`,
      ),
    ).rejects.toMatchObject({ code: "StateMismatch" });
    expect(spy).not.toHaveBeenCalled();
    expect(getSession()).toBeNull();
  });

  it("surfaces the error Cognito sends back", async () => {
    await expect(
      completeHostedSignIn(
        `${window.location.origin}/auth/callback?error=access_denied&error_description=Cancelled`,
      ),
    ).rejects.toMatchObject({ message: "Cancelled" });
  });

  it("trades the code for tokens with the saved verifier", async () => {
    const redirectedTo = captureRedirect();
    void startHostedSignIn();
    const state = (await redirectedTo()).searchParams.get("state")!;
    const verifier = savedVerifier(state);
    vi.restoreAllMocks();

    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Headers({ "Content-Type": "application/json" }),
      text: async () =>
        JSON.stringify({
          id_token: makeIdToken(),
          access_token: "a1",
          refresh_token: "r1",
          token_type: "Bearer",
          expires_in: 3600,
        }),
    } as Response);

    await completeHostedSignIn(
      `${window.location.origin}/auth/callback?code=c&state=${state}`,
    );

    const [url, init] = spy.mock.calls[0];
    expect(String(url)).toBe(
      "https://peach-test.auth.us-east-1.amazoncognito.com/oauth2/token",
    );
    expect(
      Object.fromEntries(new URLSearchParams(String(init?.body))),
    ).toMatchObject({
      grant_type: "authorization_code",
      code: "c",
      code_verifier: verifier,
    });
    expect(getSession()?.email).toBe("alice@example.com");
    expect(window.localStorage.getItem(`oidc.${state}`)).toBeNull();
  });
});
