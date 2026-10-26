import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import { OrderExplorer } from "./OrderExplorer";

afterEach(cleanup);

test("order choices change the actual saved total and included rows", () => {
  render(<OrderExplorer />);
  const output = within(screen.getByRole("region", { name: "Order summary" }));
  expect(output.getByText("120.00")).toBeTruthy();
  expect(output.queryByText("A101")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Include cancelled" }));
  expect(output.getByText("132.50")).toBeTruthy();
  expect(output.getByText("A101")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Keep first order" }));
  expect(output.getByText("125.50")).toBeTruthy();
  expect(output.getByText("35.00")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Exclude cancelled" }));
  expect(output.getByText("113.00")).toBeTruthy();
});

test("equivalent rounding stays visible with a concrete execution cost", () => {
  render(<OrderExplorer />);
  expect(screen.getByText("Rounding resolves itself here.")).toBeTruthy();
  expect(screen.getByText(/4 paired comparisons/)).toBeTruthy();
  expect(screen.getByText(/8 previews/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Keep first order" }));
  expect(
    screen
      .getByRole("button", { name: "Keep first order" })
      .getAttribute("aria-pressed"),
  ).toBe("true");
  expect(
    screen
      .getByRole("button", { name: "Keep last order" })
      .getAttribute("aria-pressed"),
  ).toBe("false");
});
