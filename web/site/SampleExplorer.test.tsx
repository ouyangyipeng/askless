import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import { SampleExplorer } from "./SampleExplorer";

afterEach(cleanup);

test("switching duplicates displays the corresponding saved branch", () => {
  render(<SampleExplorer />);
  const result = within(screen.getByRole("region", { name: "Sample output" }));
  expect(result.getByText("Ada Lovelace")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Keep last row" }));
  expect(result.getByText("Ada L.")).toBeTruthy();
  expect(result.queryByText("Ada Lovelace")).toBeNull();
  expect(
    screen
      .getByRole("button", { name: "Keep last row" })
      .getAttribute("aria-pressed"),
  ).toBe("true");
});

test("blocking hides the export and restoring quarantine preserves the duplicate choice", () => {
  render(<SampleExplorer />);
  fireEvent.click(screen.getByRole("button", { name: "Keep last row" }));
  fireEvent.click(screen.getByRole("button", { name: "Block entire batch" }));
  const result = within(screen.getByRole("region", { name: "Sample output" }));
  expect(result.getByText("BATCH BLOCKED")).toBeTruthy();
  expect(result.queryByRole("table")).toBeNull();
  expect(result.getByText("0")).toBeTruthy();
  fireEvent.click(
    screen.getByRole("button", { name: "Quarantine & continue" }),
  );
  expect(result.getByText("Ada L.")).toBeTruthy();
  expect(result.getByText("4")).toBeTruthy();
});
