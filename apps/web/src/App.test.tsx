import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { App } from "./App";

vi.mock("./api/client", () => ({
  api: { GET: vi.fn().mockResolvedValue({ data: { status: "ok" } }) },
}));

test("shows API health from the generated client", async () => {
  render(<App />);
  expect(await screen.findByText(/API health: ok/)).toBeInTheDocument();
});
