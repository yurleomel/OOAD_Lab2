import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ItemFormDialog } from "@/components/item-form-dialog";
import { api, type AiSuggestion } from "@/lib/api";
import { ParseError, parseAgenda } from "@/lib/parser";
import { makeItem, renderWithQuery } from "./utils";

vi.mock("@/lib/parser", async (original) => ({
  ...(await original<typeof import("@/lib/parser")>()),
  parseAgenda: vi.fn(),
}));

const SUGGESTION: AiSuggestion = {
  agenda: {
    title: "Pricing sync",
    starts_at: null,
    duration_minutes: 45,
    items: [
      { topic: "New Pro plans", owner: "Olena", minutes: 15 },
      { topic: "Customer feedback", owner: "Taras", minutes: null },
    ],
    action_items: [
      { task: "Competitor comparison", owner: "Taras", due: "2026-10-23" },
    ],
    language: "en",
  },
  model: "us.anthropic.claude-haiku-4-5-20251001-v1:0",
  prompt_version: "agenda-v1",
};

function renderDialog(item = null as ReturnType<typeof makeItem> | null) {
  renderWithQuery(<ItemFormDialog open onOpenChange={() => {}} item={item} />);
}

async function pasteAndParse() {
  await userEvent.click(
    screen.getByRole("button", { name: "Paste an agenda" }),
  );
  await userEvent.type(
    screen.getByLabelText("Paste an agenda"),
    "Mon 10:00 pricing sync",
  );
  await userEvent.click(screen.getByRole("button", { name: "Parse" }));
}

beforeEach(() =>
  vi.stubEnv("NEXT_PUBLIC_PARSER_URL", "https://parser.example"),
);
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

describe("Paste an agenda", () => {
  it("is not offered without a parser, but typing an agenda is", () => {
    vi.stubEnv("NEXT_PUBLIC_PARSER_URL", "");
    renderDialog();

    expect(
      screen.queryByRole("button", { name: "Paste an agenda" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Add agenda" }),
    ).toBeInTheDocument();
  });

  it("pre-fills the form, marks what the model filled, and saves it with the suggestion", async () => {
    vi.mocked(parseAgenda).mockResolvedValue(SUGGESTION);
    const create = vi
      .spyOn(api, "createItem")
      .mockResolvedValue(makeItem({ name: "Pricing sync" }));
    renderDialog();

    await pasteAndParse();

    expect(await screen.findByLabelText("Topic 1")).toHaveValue(
      "New Pro plans",
    );
    expect(screen.getByLabelText("Owner of topic 1")).toHaveValue("Olena");
    expect(screen.getByLabelText("Minutes for topic 2")).toHaveValue("");
    expect(screen.getByLabelText(/^Title/)).toHaveValue("Pricing sync");
    expect(screen.getByLabelText(/^Duration/)).toHaveValue("45");
    expect(screen.getByLabelText("Due date of action item 1")).toHaveValue(
      "2026-10-23",
    );
    // Empty fields stay empty and unmarked; filled ones are marked.
    expect(screen.getByLabelText("Topic 1")).toHaveAttribute("data-suggested");
    expect(screen.getByLabelText("Minutes for topic 2")).not.toHaveAttribute(
      "data-suggested",
    );
    expect(
      screen.getByText(/Suggested by Claude Haiku 4\.5/),
    ).toBeInTheDocument();

    // A correction removes the mark: the user has checked that field.
    const owner = screen.getByLabelText("Owner of topic 2");
    await userEvent.clear(owner);
    await userEvent.type(owner, "Taras K.");
    expect(owner).not.toHaveAttribute("data-suggested");

    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
    const payload = create.mock.calls[0][0];
    expect(payload.name).toBe("Pricing sync");
    expect(payload.agenda?.items[1]).toEqual({
      topic: "Customer feedback",
      owner: "Taras K.",
      minutes: null,
    });
    expect(payload.agenda?.duration_minutes).toBe(45);
    expect(payload.agenda?.action_items[0].due).toBe("2026-10-23");
    expect(payload.ai_suggestion).toEqual(SUGGESTION);
  });

  it("keeps a name the user already typed", async () => {
    vi.mocked(parseAgenda).mockResolvedValue(SUGGESTION);
    renderDialog();

    await userEvent.type(screen.getByLabelText("Title"), "Weekly pricing");
    await pasteAndParse();

    await screen.findByLabelText("Topic 1");
    expect(screen.getByLabelText("Title")).toHaveValue("Weekly pricing");
  });

  it("shows progress and can be cancelled", async () => {
    vi.mocked(parseAgenda).mockImplementation(
      (_text, signal) =>
        new Promise((_, reject) =>
          signal?.addEventListener("abort", () =>
            reject(new ParseError("cancelled", "Cancelled")),
          ),
        ),
    );
    renderDialog();

    await pasteAndParse();
    expect(screen.getByRole("status")).toHaveTextContent("Reading the agenda");

    await userEvent.click(
      screen.getByRole("button", { name: "Cancel parsing" }),
    );

    expect(await screen.findByRole("button", { name: "Parse" })).toBeEnabled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Paste an agenda")).toHaveValue(
      "Mon 10:00 pricing sync",
    );
  });

  it("explains an error and offers typing it by hand", async () => {
    vi.mocked(parseAgenda).mockRejectedValue(
      new ParseError("no_agenda", "No agenda found in this text."),
    );
    renderDialog();

    await pasteAndParse();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("No agenda found");
    await userEvent.click(
      within(alert).getByRole("button", { name: "Type it by hand" }),
    );
    expect(screen.getByLabelText("Topic 1")).toHaveValue("");
  });

  it("removes a saved agenda", async () => {
    const update = vi.spyOn(api, "updateItem").mockResolvedValue(makeItem());
    renderDialog(
      makeItem({
        agenda: {
          starts_at: null,
          duration_minutes: null,
          items: [{ topic: "Old topic", owner: null, minutes: null }],
          action_items: [],
        },
      }),
    );

    expect(screen.getByLabelText("Topic 1")).toHaveValue("Old topic");
    expect(screen.getByLabelText("Topic 1")).not.toHaveAttribute(
      "data-suggested",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Remove agenda" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(update).toHaveBeenCalledTimes(1));
    expect(update.mock.calls[0][1].agenda).toBeNull();
    expect(update.mock.calls[0][1]).not.toHaveProperty("ai_suggestion");
  });
});
