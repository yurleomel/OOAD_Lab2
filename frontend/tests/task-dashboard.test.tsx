import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { summarize, TaskDashboard } from "@/components/task-dashboard";
import { api } from "@/lib/api";
import { fetchAllItems } from "@/lib/use-items";
import { makeItem, renderWithQuery, signInAs } from "./utils";

// Wednesday 30 September 2026, noon, local time; the week began Monday the 28th.
const now = new Date(2026, 8, 30, 12);
const at = (day: number, hour = 9) =>
  new Date(2026, 8, day, hour).toISOString();

describe("summarize", () => {
  it("derives every dashboard figure from the list", () => {
    const summary = summarize(
      [
        makeItem({ id: "a", status: "todo", created_at: at(27, 23) }),
        makeItem({
          id: "b",
          status: "in_progress",
          created_at: at(29),
          updated_at: at(29),
        }),
        makeItem({
          id: "c",
          status: "in_progress",
          created_at: at(28),
          updated_at: at(30),
        }),
        makeItem({
          id: "d",
          status: "done",
          created_at: at(20),
          updated_at: at(28, 0),
        }),
        makeItem({
          id: "e",
          status: "done",
          created_at: at(20),
          updated_at: at(27),
        }),
        makeItem({
          id: "f",
          status: "done",
          created_at: at(30),
          updated_at: at(30),
        }),
      ],
      now,
    );

    expect(summary.total).toBe(6);
    expect(summary.counts).toEqual({ todo: 1, in_progress: 2, done: 3 });
    expect(summary.donePercent).toBe(50);
    // b, c and f were created since Monday; a on Sunday night was not.
    expect(summary.addedThisWeek).toBe(3);
    // d at Monday 00:00 counts, e on Sunday does not.
    expect(summary.completedThisWeek).toBe(2);
    expect(summary.inProgress.map((item) => item.id)).toEqual(["c", "b"]);
    expect(summary.recentlyDone.map((item) => item.id)).toEqual([
      "f",
      "d",
      "e",
    ]);
  });

  it("keeps each list to five", () => {
    const items = Array.from({ length: 8 }, (_, index) =>
      makeItem({
        id: String(index),
        status: "done",
        updated_at: at(index + 1),
      }),
    );
    expect(summarize(items, now).recentlyDone).toHaveLength(5);
  });

  it("is zero, not NaN, with no tasks", () => {
    expect(summarize([], now).donePercent).toBe(0);
  });
});

describe("TaskDashboard", () => {
  it("greets the person and shows their progress", async () => {
    signInAs({ name: "Alice Liddell" });
    vi.spyOn(api, "listItems").mockResolvedValue({
      items: [
        makeItem({ id: "1", status: "done" }),
        makeItem({ id: "2", status: "in_progress", name: "Draft" }),
        makeItem({ id: "3", status: "todo" }),
        makeItem({ id: "4", status: "done" }),
      ],
      total: 4,
    });
    renderWithQuery(<TaskDashboard />);

    expect(
      await screen.findByRole("heading", { level: 1, name: /, Alice$/ }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("progressbar", { name: "Tasks done" }),
    ).toHaveAttribute("aria-valuenow", "50");
    const byStatus = screen.getByRole("region", { name: "By status" });
    expect(
      within(byStatus).getByLabelText("Done: 2 tasks, 50%"),
    ).toBeInTheDocument();
    const inProgress = screen.getByRole("region", { name: "In progress" });
    expect(within(inProgress).getByText("Draft")).toBeInTheDocument();
  });

  it("invites a first task when there are none", async () => {
    signInAs();
    vi.spyOn(api, "listItems").mockResolvedValue({ items: [], total: 0 });
    renderWithQuery(<TaskDashboard />);

    await userEvent.click(
      await screen.findByRole("button", { name: "Create a task" }),
    );
    expect(
      await screen.findByRole("heading", { name: "New task" }),
    ).toBeInTheDocument();
  });

  it("offers a retry when loading fails", async () => {
    signInAs();
    vi.spyOn(api, "listItems").mockRejectedValue(
      new Error("Could not reach the API"),
    );
    renderWithQuery(<TaskDashboard />);

    expect(await screen.findByText("Could not load tasks")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});

describe("fetchAllItems", () => {
  it("pages through past the API's limit of 100", async () => {
    const page = (from: number, count: number) =>
      Array.from({ length: count }, (_, index) =>
        makeItem({ id: String(from + index) }),
      );
    const spy = vi
      .spyOn(api, "listItems")
      .mockResolvedValueOnce({ items: page(0, 100), total: 130 })
      .mockResolvedValueOnce({ items: page(100, 30), total: 130 });

    const all = await fetchAllItems();

    expect(all.items).toHaveLength(130);
    expect(all.total).toBe(130);
    expect(spy.mock.calls).toEqual([
      [{ limit: 100, offset: 0 }],
      [{ limit: 100, offset: 100 }],
    ]);
  });
});
