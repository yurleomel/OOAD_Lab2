import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";

import { TaskDialogsProvider } from "@/components/task-dialogs";
import type { Item } from "@/lib/api";

/** Render with a fresh QueryClient - so tests never share cache state - and the
 *  task dialogs every signed-in page relies on. */
export function renderWithQuery(ui: ReactElement, options?: RenderOptions) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <TaskDialogsProvider>{children}</TaskDialogsProvider>
      </QueryClientProvider>
    );
  }

  return render(ui, { wrapper: Wrapper, ...options });
}

export function makeItem(overrides: Partial<Item> = {}): Item {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    name: "Example",
    description: "An example item",
    status: "todo",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

/** An unsigned JWT with the given claims - the browser never verifies, the API does. */
export function makeIdToken(claims: Record<string, unknown> = {}): string {
  const encode = (value: object) =>
    btoa(
      String.fromCharCode(...new TextEncoder().encode(JSON.stringify(value))),
    )
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "");
  const payload = {
    sub: "alice-sub",
    email: "alice@example.com",
    name: "Alice Liddell",
    token_use: "id",
    exp: Math.floor(Date.now() / 1000) + 3600,
    ...claims,
  };
  return `${encode({ alg: "RS256", kid: "test" })}.${encode(payload)}.signature`;
}

/** Stores a session the way lib/auth does after a successful sign-in. */
export function signInAs(claims: Record<string, unknown> = {}) {
  const idToken = makeIdToken(claims);
  window.localStorage.setItem(
    "peach.session",
    JSON.stringify({
      idToken,
      refreshToken: "refresh-token",
      expiresAt: Date.now() + 3_600_000,
    }),
  );
  return idToken;
}
