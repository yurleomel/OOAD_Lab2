import { aiSuggestionSchema, type AiSuggestion } from "@/lib/api";
import { getIdToken, signOut } from "@/lib/auth";

/** The agenda parser's function URL (make infra-env), compiled in at build time.
 *  Empty in a build without one: the paste box is then not offered at all. */
export function parserUrl(): string {
  return (process.env.NEXT_PUBLIC_PARSER_URL ?? "").replace(/\/+$/, "");
}

/** The parser refuses longer text before the model sees it (413). */
export const MAX_PASTE_CHARS = 10_000;

export type ParseErrorKind =
  | "too_long"
  | "no_agenda"
  | "busy"
  | "network"
  | "signed_out"
  | "failed"
  | "cancelled";

export class ParseError extends Error {
  constructor(
    readonly kind: ParseErrorKind,
    message: string,
  ) {
    super(message);
    this.name = "ParseError";
  }
}

const messages: Record<Exclude<ParseErrorKind, "cancelled">, string> = {
  too_long: `The text is too long. Paste at most ${MAX_PASTE_CHARS.toLocaleString("en")} characters.`,
  no_agenda:
    "No agenda found in this text. Paste the part with the topics, or type them by hand.",
  busy: "The parser is busy right now. Try again in a minute, or type the agenda by hand.",
  network: "Could not reach the parser. Check the connection and try again.",
  signed_out: "You are signed out. Sign in again to paste an agenda.",
  failed:
    "The parser could not read an agenda from this text. Try again, or type it by hand.",
};

/** The user's own date and time zone: "Monday" in the text means theirs, not the
 *  server's, which runs in UTC. */
function localContext() {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return {
    today: `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`,
    tz: Intl.DateTimeFormat().resolvedOptions().timeZone,
  };
}

/** Ask the parser for a suggestion. It never writes: saving goes through the API. */
export async function parseAgenda(
  text: string,
  signal?: AbortSignal,
): Promise<AiSuggestion> {
  const token = await getIdToken();
  if (!token) throw new ParseError("signed_out", messages.signed_out);

  let response: Response;
  try {
    response = await fetch(parserUrl(), {
      method: "POST",
      cache: "no-store",
      signal,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ text, ...localContext() }),
    });
  } catch {
    if (signal?.aborted) throw new ParseError("cancelled", "Cancelled");
    throw new ParseError("network", messages.network);
  }

  if (response.ok) {
    const parsed = aiSuggestionSchema.safeParse(await response.json());
    if (parsed.success) return parsed.data;
    throw new ParseError("failed", messages.failed);
  }

  const code = await response
    .json()
    .then((body) => (typeof body?.error === "string" ? body.error : null))
    .catch(() => null);
  if (response.status === 401) {
    signOut();
    throw new ParseError("signed_out", messages.signed_out);
  }
  if (response.status === 413)
    throw new ParseError("too_long", messages.too_long);
  if (response.status === 422 && code === "no_agenda") {
    throw new ParseError("no_agenda", messages.no_agenda);
  }
  if (response.status === 429 || response.status === 503) {
    throw new ParseError("busy", messages.busy);
  }
  throw new ParseError("failed", messages.failed);
}
