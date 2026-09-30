/**
 * Sign-in against the Cognito user pool, straight from the browser.
 *
 * Email + password use Cognito's public API (InitiateAuth, SignUp, ...), which
 * an app client without a secret may call directly. Google goes through the
 * pool's hosted domain with the OAuth code flow + PKCE. Tokens live in
 * localStorage; the ID token is what the API accepts, and it is renewed from
 * the refresh token a minute before it expires.
 *
 * None of this is a security boundary - the API checks every token itself.
 */
import { useSyncExternalStore } from "react";

const config = {
  region: process.env.NEXT_PUBLIC_COGNITO_REGION || "us-east-1",
  clientId: process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID ?? "",
  domain: (process.env.NEXT_PUBLIC_COGNITO_DOMAIN ?? "").replace(
    /^https?:\/\//,
    "",
  ),
  googleEnabled: process.env.NEXT_PUBLIC_COGNITO_GOOGLE_ENABLED === "true",
};

/** False until make deploy-cognito has written the pool ids and the app was rebuilt. */
export const authConfigured = Boolean(config.clientId);
export const googleEnabled =
  authConfigured && config.googleEnabled && Boolean(config.domain);

const STORAGE_KEY = "peach.session";
const PKCE_KEY = "peach.pkce";
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
      "This account needs a sign-in step Peach does not support.",
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
  // Several requests can notice the expiry at once; they share one refresh.
  refreshing ??= refresh(tokens).finally(() => {
    refreshing = null;
  });
  return refreshing;
}

export function signOut() {
  writeTokens(null);
}

/* --- Google, through the hosted domain ----------------------------------- */

function base64Url(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function randomString(byteCount: number): string {
  return base64Url(crypto.getRandomValues(new Uint8Array(byteCount)));
}

function redirectUri(): string {
  return `${window.location.origin}/auth/callback`;
}

/** The hosted-domain URL that starts Google sign-in; remembers the PKCE verifier. */
export async function googleSignInUrl(): Promise<string> {
  const verifier = randomString(48);
  const state = randomString(16);
  window.sessionStorage.setItem(PKCE_KEY, JSON.stringify({ verifier, state }));
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(verifier),
  );
  const params = new URLSearchParams({
    identity_provider: "Google",
    response_type: "code",
    client_id: config.clientId,
    redirect_uri: redirectUri(),
    scope: "openid email profile",
    state,
    code_challenge: base64Url(new Uint8Array(digest)),
    code_challenge_method: "S256",
  });
  return `https://${config.domain}/oauth2/authorize?${params}`;
}

export async function startGoogleSignIn(): Promise<void> {
  window.location.assign(await googleSignInUrl());
}

/** Finishes the redirect from Google: checks state, trades the code for tokens. */
export async function completeGoogleSignIn(
  params: URLSearchParams,
): Promise<void> {
  const failure = params.get("error_description") ?? params.get("error");
  if (failure) throw new AuthError("OAuthError", failure);

  const saved = window.sessionStorage.getItem(PKCE_KEY);
  window.sessionStorage.removeItem(PKCE_KEY);
  const pkce = saved
    ? (JSON.parse(saved) as { verifier: string; state: string })
    : null;
  const code = params.get("code");
  if (!code || !pkce || pkce.state !== params.get("state")) {
    throw new AuthError(
      "StateMismatch",
      "This sign-in link has expired. Start again.",
    );
  }

  const response = await fetch(`https://${config.domain}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      client_id: config.clientId,
      code,
      redirect_uri: redirectUri(),
      code_verifier: pkce.verifier,
    }),
  }).catch(() => null);
  if (!response?.ok) {
    throw new AuthError(
      "TokenExchangeFailed",
      "Google sign-in could not be completed. Try again.",
    );
  }
  const tokens = (await response.json()) as {
    id_token: string;
    refresh_token: string;
  };
  saveSession(tokens.id_token, tokens.refresh_token);
}
