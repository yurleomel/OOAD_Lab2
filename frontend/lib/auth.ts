/**
 * Sign-in against the Cognito user pool, straight from the browser.
 *
 * Email + password use Cognito's public API (InitiateAuth, SignUp, ...), which
 * an app client without a secret may call directly. Google, and the managed
 * login page that /login opens, go through the pool's hosted domain with the
 * OAuth code flow + PKCE, driven by oidc-client-ts. Tokens live in
 * localStorage; the ID token is what the API accepts, and it is renewed from
 * the refresh token a minute before it expires.
 *
 * None of this is a security boundary - the API checks every token itself.
 */
import { UserManager } from "oidc-client-ts";
import { useSyncExternalStore } from "react";

import {
  authConfigured,
  config,
  googleEnabled,
  hostedSignInConfigured,
} from "@/lib/auth-config";

export { authConfigured, googleEnabled, hostedSignInConfigured };

const STORAGE_KEY = "peach.session";
const REFRESH_MARGIN_MS = 60_000;

export type Session = { sub: string; email: string; name: string };

type StoredTokens = {
  idToken: string;
  refreshToken: string;
  expiresAt: number;
};

type AuthenticationResult = {
  IdToken: string;
  RefreshToken?: string;
  ExpiresIn: number;
};

export class AuthError extends Error {
  constructor(
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "AuthError";
  }
}

const friendlyMessages: Record<string, string> = {
  NotAuthorizedException: "Incorrect email or password.",
  UserNotFoundException: "Incorrect email or password.",
  UserNotConfirmedException: "Confirm your email before logging in.",
  UsernameExistsException: "An account with this email already exists.",
  CodeMismatchException: "That code is not right. Check the email and retry.",
  ExpiredCodeException: "That code has expired. Send a new one.",
  LimitExceededException: "Too many attempts. Wait a minute and try again.",
  TooManyRequestsException: "Too many attempts. Wait a minute and try again.",
};

async function cognito<T>(action: string, body: object): Promise<T> {
  let response: Response;
  try {
    response = await fetch(
      `https://cognito-idp.${config.region}.amazonaws.com/`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/x-amz-json-1.1",
          "X-Amz-Target": `AWSCognitoIdentityProviderService.${action}`,
        },
        body: JSON.stringify(body),
      },
    );
  } catch {
    throw new AuthError("NetworkError", "Could not reach the sign-in service.");
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    // "NotAuthorizedException", sometimes namespaced as "...#NotAuthorizedException".
    const code = String(data.__type ?? "UnknownError")
      .split("#")
      .pop()!;
    throw new AuthError(
      code,
      friendlyMessages[code] ?? data.message ?? "Something went wrong.",
    );
  }
  return data as T;
}

/* --- token storage ------------------------------------------------------- */

function readRaw(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function readTokens(): StoredTokens | null {
  const raw = readRaw();
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StoredTokens;
  } catch {
    return null;
  }
}

function writeTokens(tokens: StoredTokens | null) {
  try {
    if (tokens) {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(tokens));
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // Storage blocked (private mode, quota): the session lasts this page only.
  }
  listeners.forEach((listener) => listener());
}

/** The claims of a JWT, unverified - the API is what verifies. */
function decodeClaims(token: string): Record<string, unknown> {
  const part = token.split(".")[1] ?? "";
  const base64 = part.replace(/-/g, "+").replace(/_/g, "/");
  const bytes = Uint8Array.from(atob(base64), (char) => char.charCodeAt(0));
  return JSON.parse(new TextDecoder().decode(bytes));
}

function saveSession(idToken: string, refreshToken: string): StoredTokens {
  const exp = Number(decodeClaims(idToken).exp);
  const tokens = { idToken, refreshToken, expiresAt: exp * 1000 };
  writeTokens(tokens);
  return tokens;
}

function toSession(raw: string): Session | null {
  try {
    const { idToken } = JSON.parse(raw) as StoredTokens;
    const claims = decodeClaims(idToken);
    const email = String(claims.email ?? "");
    const name =
      typeof claims.name === "string" && claims.name
        ? claims.name
        : email.split("@")[0];
    return { sub: String(claims.sub), email, name };
  } catch {
    return null;
  }
}

/* --- session as an external store for React ------------------------------ */

const listeners = new Set<() => void>();

function subscribe(listener: () => void) {
  listeners.add(listener);
  // Another tab signing in or out changes this one too.
  const onStorage = (event: StorageEvent) => {
    if (event.key === null || event.key === STORAGE_KEY) listener();
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

// useSyncExternalStore needs the same object back while nothing has changed.
let cachedRaw: string | null | undefined;
let cachedSession: Session | null = null;

export function getSession(): Session | null {
  const raw = readRaw();
  if (raw !== cachedRaw) {
    cachedRaw = raw;
    cachedSession = raw ? toSession(raw) : null;
  }
  return cachedSession;
}

/** The signed-in person, or null. Always null while prerendering. */
export function useSession(): Session | null {
  return useSyncExternalStore(subscribe, getSession, () => null);
}

const noopSubscribe = () => () => {};

/** False during prerender and hydration, true once the browser has taken over. */
export function useHydrated(): boolean {
  return useSyncExternalStore(
    noopSubscribe,
    () => true,
    () => false,
  );
}

/* --- email + password ---------------------------------------------------- */

export async function signIn(email: string, password: string): Promise<void> {
  const data = await cognito<{
    AuthenticationResult?: AuthenticationResult;
    ChallengeName?: string;
  }>("InitiateAuth", {
    AuthFlow: "USER_PASSWORD_AUTH",
    ClientId: config.clientId,
    AuthParameters: { USERNAME: email, PASSWORD: password },
  });
  if (!data.AuthenticationResult?.RefreshToken) {
    throw new AuthError(
      data.ChallengeName ?? "UnsupportedChallenge",
      "This account needs a sign-in step Lanora does not support.",
    );
  }
  saveSession(
    data.AuthenticationResult.IdToken,
    data.AuthenticationResult.RefreshToken,
  );
}

/** Creates the account; Cognito then emails a code to confirm it. */
export async function signUp(input: {
  name: string;
  email: string;
  password: string;
}): Promise<{ confirmed: boolean }> {
  const data = await cognito<{ UserConfirmed: boolean }>("SignUp", {
    ClientId: config.clientId,
    Username: input.email,
    Password: input.password,
    UserAttributes: [
      { Name: "email", Value: input.email },
      { Name: "name", Value: input.name },
    ],
  });
  return { confirmed: data.UserConfirmed };
}

export async function confirmSignUp(email: string, code: string) {
  await cognito("ConfirmSignUp", {
    ClientId: config.clientId,
    Username: email,
    ConfirmationCode: code.trim(),
  });
}

export async function resendCode(email: string) {
  await cognito("ResendConfirmationCode", {
    ClientId: config.clientId,
    Username: email,
  });
}

/* --- local development ---------------------------------------------------- */

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * `docker compose up` without a Cognito pool: any email, no password. The API
 * signs the token itself, and only while it runs as local development.
 */
export async function signInLocally(email: string, name: string) {
  let response: Response;
  try {
    response = await fetch(`${apiUrl}/local/sign-in`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, name }),
    });
  } catch {
    throw new AuthError("NetworkError", "Could not reach the API.");
  }
  if (response.status === 404) {
    throw new AuthError(
      "LocalSignInOff",
      "This API does not offer local sign-in: it needs APP_ENV=development and no Cognito pool.",
    );
  }
  if (!response.ok) {
    throw new AuthError(
      "LocalSignInFailed",
      response.status === 422
        ? "Enter a valid email address."
        : `Sign-in failed (${response.status}).`,
    );
  }
  const { id_token } = (await response.json()) as { id_token: string };
  // No refresh token: when this one runs out, sign in again.
  saveSession(id_token, "");
}

/* --- tokens for the API -------------------------------------------------- */

let refreshing: Promise<string | null> | null = null;

async function refresh(tokens: StoredTokens): Promise<string | null> {
  try {
    const data = await cognito<{ AuthenticationResult?: AuthenticationResult }>(
      "InitiateAuth",
      {
        AuthFlow: "REFRESH_TOKEN_AUTH",
        ClientId: config.clientId,
        AuthParameters: { REFRESH_TOKEN: tokens.refreshToken },
      },
    );
    if (!data.AuthenticationResult) throw new AuthError("NoTokens", "");
    return saveSession(
      data.AuthenticationResult.IdToken,
      // Cognito hands back a new refresh token only when rotation is on.
      data.AuthenticationResult.RefreshToken ?? tokens.refreshToken,
    ).idToken;
  } catch (error) {
    // The pool said no - revoked, expired, account deleted - so the session is
    // over. A network failure is not a verdict; keep the session for a retry.
    if (!(error instanceof AuthError) || error.code !== "NetworkError") {
      signOut();
    }
    return null;
  }
}

/** A valid ID token, renewed first if it is about to expire; null when signed out. */
export async function getIdToken(): Promise<string | null> {
  const tokens = readTokens();
  if (!tokens) return null;
  if (tokens.expiresAt - REFRESH_MARGIN_MS > Date.now()) return tokens.idToken;
  if (!tokens.refreshToken) {
    // A local sign-in has nothing to renew it with.
    signOut();
    return null;
  }
  // Several requests can notice the expiry at once; they share one refresh.
  refreshing ??= refresh(tokens).finally(() => {
    refreshing = null;
  });
  return refreshing;
}

export function signOut() {
  writeTokens(null);
}

/* --- The hosted domain: managed login and Google ------------------------- */

let userManager: UserManager | null = null;

/**
 * oidc-client-ts does the code flow: it keeps state + the PKCE verifier in
 * sessionStorage, redirects, checks the state on the way back and trades the
 * code for tokens. The endpoints are given rather than discovered, so sign-in
 * starts without a round trip; they are what the pool's discovery document lists.
 */
function oidc(): UserManager {
  const authority = `https://cognito-idp.${config.region}.amazonaws.com/${config.userPoolId}`;
  const origin = `https://${config.domain}`;
  userManager ??= new UserManager({
    authority,
    client_id: config.clientId,
    redirect_uri: `${window.location.origin}/auth/callback`,
    response_type: "code",
    scope: "openid email profile",
    metadata: {
      issuer: authority,
      authorization_endpoint: `${origin}/oauth2/authorize`,
      token_endpoint: `${origin}/oauth2/token`,
      userinfo_endpoint: `${origin}/oauth2/userInfo`,
      revocation_endpoint: `${origin}/oauth2/revoke`,
      jwks_uri: `${authority}/.well-known/jwks.json`,
    },
    // The session store below renews tokens; the library only signs in.
    automaticSilentRenew: false,
  });
  return userManager;
}

/**
 * Sends the browser to the hosted domain. With a provider it goes straight
 * there; without one it opens the managed login page (email + password, or
 * Continue with Google).
 */
export async function startHostedSignIn(provider?: "Google"): Promise<void> {
  await oidc().signinRedirect(
    provider ? { extraQueryParams: { identity_provider: provider } } : {},
  );
}

export const startGoogleSignIn = () => startHostedSignIn("Google");

/**
 * Where to send the browser on log out, or null to stay in the app. Cognito
 * has no OIDC end-session endpoint; its /logout clears the hosted domain's own
 * cookie, without which the next /login would sign the same user straight back in.
 */
export function hostedLogoutUrl(): string | null {
  if (!authConfigured || !config.domain) return null;
  const params = new URLSearchParams({
    client_id: config.clientId,
    logout_uri: `${window.location.origin}/`,
  });
  return `https://${config.domain}/logout?${params}`;
}

/** Finishes the redirect from the hosted domain: checks state, trades the code for tokens. */
export async function completeHostedSignIn(url: string): Promise<void> {
  const failure = new URL(url).searchParams;
  const reason = failure.get("error_description") ?? failure.get("error");
  if (reason) throw new AuthError("OAuthError", reason);

  let user;
  try {
    user = await oidc().signinRedirectCallback(url);
  } catch (error) {
    const message = error instanceof Error ? error.message : "";
    throw message.includes("No matching state")
      ? new AuthError(
          "StateMismatch",
          "This sign-in link has expired. Start again.",
        )
      : new AuthError(
          "TokenExchangeFailed",
          "Sign-in could not be completed. Try again.",
        );
  }
  if (!user.id_token) {
    throw new AuthError(
      "NoTokens",
      "Sign-in could not be completed. Try again.",
    );
  }
  saveSession(user.id_token, user.refresh_token ?? "");
  // The tokens now live in the session store; drop the library's copy.
  await oidc().removeUser();
}
