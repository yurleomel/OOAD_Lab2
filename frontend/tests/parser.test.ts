import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ParseError, parseAgenda } from "@/lib/parser";

vi.mock("@/lib/auth", () => ({
  getIdToken: vi.fn(async () => "id-token"),
  signOut: vi.fn(),
}));

const RESULT = {
  agenda: {
    title: "Pricing sync",
    starts_at: "2026-10-19T10:00:00+03:00",
    duration_minutes: 45,
    items: [{ topic: "Pro plans", owner: "Olena", minutes: 15 }],
    action_items: [],
    language: "en",
  },
  model: "us.anthropic.claude-haiku-4-5-20251001-v1:0",
  prompt_version: "agenda-v1",
};

function mockFetch(body: unknown, status = 200) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response);
}

beforeEach(() =>
  vi.stubEnv("NEXT_PUBLIC_PARSER_URL", "https://parser.example/"),
);
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

describe("parseAgenda", () => {
  it("posts the text with the user's date and time zone, signed in", async () => {
    const spy = mockFetch(RESULT);

    await expect(parseAgenda("Mon 10:00 pricing")).resolves.toEqual(RESULT);

    const [url, init] = spy.mock.calls[0];
    expect(url).toBe("https://parser.example");
    expect(init?.method).toBe("POST");
    expect((init?.headers as Record<string, string>).Authorization).toBe(
      "Bearer id-token",
    );
    const body = JSON.parse(init?.body as string);
    expect(body.text).toBe("Mon 10:00 pricing");
    expect(body.today).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(body.tz).toBe(Intl.DateTimeFormat().resolvedOptions().timeZone);
  });

  it.each([
    [413, { error: "too_long" }, "too_long"],
    [422, { error: "no_agenda" }, "no_agenda"],
    [422, { error: "invalid_output" }, "failed"],
    [429, { error: "busy" }, "busy"],
    [503, { error: "unavailable" }, "busy"],
    [401, { error: "unauthorized" }, "signed_out"],
  ])("maps %i %o to %s", async (status, body, kind) => {
    mockFetch(body, status);
    await expect(parseAgenda("text")).rejects.toMatchObject({ kind });
  });

  it("tells a network failure from a cancel", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("offline"));
    await expect(parseAgenda("text")).rejects.toMatchObject({
      kind: "network",
    });

    const controller = new AbortController();
    controller.abort();
    await expect(parseAgenda("text", controller.signal)).rejects.toMatchObject({
      kind: "cancelled",
    });
  });

  it("rejects an answer that does not match the schema", async () => {
    mockFetch({ agenda: { items: "nope" } });
    await expect(parseAgenda("text")).rejects.toBeInstanceOf(ParseError);
  });
});
