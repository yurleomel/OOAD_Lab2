import { z } from "zod";

import { getIdToken, signOut } from "@/lib/auth";

/** Browser code must reach the API through the published port; server components
 *  resolve the Compose service name instead. */
export function apiBaseUrl(): string {
  if (typeof window === "undefined") {
    return process.env.INTERNAL_API_URL ?? "http://backend:8000";
  }
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInit,
): Promise<T> {
  // Every API route needs a signed-in user; don't send what would bounce.
  const token = await getIdToken();
  if (!token) throw new ApiError(401, "You are signed out");

  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      ...init,
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError(0, "Could not reach the API");
  }

  // The API no longer accepts this session (revoked, or the pool changed):
  // drop it, and the auth gate sends the user back to the login page.
  if (response.status === 401) signOut();

  if (!response.ok) {
    const detail = await response
      .json()
      .then((body) => (typeof body?.detail === "string" ? body.detail : null))
      .catch(() => null);
    throw new ApiError(
      response.status,
      detail ?? `Request failed (${response.status})`,
    );
  }

  if (response.status === 204) {
    return schema.parse(undefined);
  }
  return schema.parse(await response.json());
}

/* --- schemas mirroring the API contract in README section 5 --- */

export const itemStatuses = ["todo", "in_progress", "done"] as const;
export const itemStatusSchema = z.enum(itemStatuses);

/* The agenda of a task (backend/app/schemas/agenda.py). */
export const agendaItemSchema = z.object({
  topic: z.string(),
  owner: z.string().nullable(),
  minutes: z.number().int().nullable(),
});

export const actionItemSchema = z.object({
  task: z.string(),
  owner: z.string().nullable(),
  due: z.string().nullable(), // YYYY-MM-DD
});

export const agendaSchema = z.object({
  starts_at: z.string().nullable(), // ISO 8601 with an offset
  duration_minutes: z.number().int().nullable(),
  items: z.array(agendaItemSchema),
  action_items: z.array(actionItemSchema),
});

/** What the parser returns: the agenda, plus the task's title and the language. */
export const parsedAgendaSchema = agendaSchema.extend({
  title: z.string().nullable(),
  language: z.string(),
});

/** The parser's answer, and what the API stores next to the saved agenda. */
export const aiSuggestionSchema = z.object({
  agenda: parsedAgendaSchema,
  model: z.string(),
  prompt_version: z.string(),
});

export const itemSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().nullable(),
  status: itemStatusSchema,
  agenda: agendaSchema.nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const itemListSchema = z.object({
  items: z.array(itemSchema),
  total: z.number().int(),
});

export const healthSchema = z.object({
  status: z.string(),
  database: z.string(),
});

export const itemInputSchema = z.object({
  name: z.string().min(1, "Name is required").max(120, "Name is too long"),
  description: z.string().max(2000, "Description is too long").optional(),
  status: itemStatusSchema,
});

export type ItemStatus = z.infer<typeof itemStatusSchema>;
export type Item = z.infer<typeof itemSchema>;
export type ItemList = z.infer<typeof itemListSchema>;
export type Health = z.infer<typeof healthSchema>;
export type ItemInput = z.infer<typeof itemInputSchema>;
export type Agenda = z.infer<typeof agendaSchema>;
export type ParsedAgenda = z.infer<typeof parsedAgendaSchema>;
export type AiSuggestion = z.infer<typeof aiSuggestionSchema>;

/** What the dialog saves: the task, its agenda (null removes it) and, after a
 *  paste, what the parser suggested - the API keeps it for comparison. */
export type ItemPayload = ItemInput & {
  agenda?: Agenda | null;
  ai_suggestion?: AiSuggestion;
};

/* --- endpoints --- */

export const api = {
  readiness: () => request("/api/v1/health/ready", healthSchema),

  listItems: (params: { limit?: number; offset?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.limit !== undefined) query.set("limit", String(params.limit));
    if (params.offset !== undefined) query.set("offset", String(params.offset));
    const suffix = query.size > 0 ? `?${query}` : "";
    return request(`/api/v1/items${suffix}`, itemListSchema);
  },

  createItem: (payload: ItemPayload) =>
    request("/api/v1/items", itemSchema, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  updateItem: (id: string, payload: Partial<ItemPayload>) =>
    request(`/api/v1/items/${id}`, itemSchema, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  deleteItem: (id: string) =>
    request(`/api/v1/items/${id}`, z.undefined(), { method: "DELETE" }),
};
