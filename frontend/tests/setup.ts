import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import { location } from "./navigation";

vi.mock("next/navigation", () => import("./navigation"));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.clearAllMocks();
  window.localStorage.clear();
  window.sessionStorage.clear();
  location.pathname = "/items";
  location.search = "";
});

// jsdom implements neither of these, and Radix relies on both.
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
} as unknown as typeof ResizeObserver;

if (!Element.prototype.hasPointerCapture) {
  Element.prototype.hasPointerCapture = () => false;
  Element.prototype.setPointerCapture = () => {};
  Element.prototype.releasePointerCapture = () => {};
}

// jsdom has no DragEvent, so drag events would lose their pointer coordinates.
globalThis.DragEvent ??=
  class extends MouseEvent {} as unknown as typeof DragEvent;
