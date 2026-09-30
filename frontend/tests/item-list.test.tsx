import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ItemList } from "@/components/item-list";
import { api } from "@/lib/api";
import { location } from "./navigation";
import { makeItem, renderWithQuery } from "./utils";

function mockItems() {
  vi.spyOn(api, "listItems").mockResolvedValue({
    items: [
      makeItem(),
      makeItem({ id: "2", name: "Second", status: "in_progress" }),
      makeItem({ id: "3", name: "Third", status: "done" }),
    ],
    total: 3,
  });
}

describe("ItemList", () => {
  it("groups tasks under their status", async () => {
    location.pathname = "/items/list";
    mockItems();
    renderWithQuery(<ItemList />);

    const group = async (name: string) => screen.findByRole("region", { name });
    expect(
      within(await group("To do")).getByText("Example"),
    ).toBeInTheDocument();
    expect(
      within(await group("In progress")).getByText("Second"),
    ).toBeInTheDocument();
    expect(within(await group("Done")).getByText("Third")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "List" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("opens the edit dialog when a row is clicked", async () => {
    mockItems();
    renderWithQuery(<ItemList />);

    await userEvent.click(
      await screen.findByRole("button", { name: "Edit Second" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Edit task" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Title")).toHaveValue("Second");
  });

  it("adds a task straight into a group", async () => {
    mockItems();
    renderWithQuery(<ItemList />);

    const done = await screen.findByRole("region", { name: "Done" });
    await userEvent.click(
      within(done).getByRole("button", { name: "Add task" }),
    );
    expect(
      await screen.findByRole("heading", { name: "New task" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Done" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("collapses a group", async () => {
    mockItems();
    renderWithQuery(<ItemList />);

    const toggle = await screen.findByRole("button", {
      name: "Collapse Done",
    });
    await userEvent.click(toggle);
    expect(screen.queryByText("Third")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Expand Done" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });
});
