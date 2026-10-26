import { createRoot } from "react-dom/client";
import { SampleExplorer } from "./SampleExplorer";
import { OrderExplorer } from "./OrderExplorer";

const mount = document.getElementById("sample-explorer");
if (mount) createRoot(mount).render(<SampleExplorer />);
const orderMount = document.getElementById("order-explorer");
if (orderMount) createRoot(orderMount).render(<OrderExplorer />);

const copyButton = document.getElementById("copy-command");
const command = document.getElementById("install-command");
const status = document.getElementById("copy-status");
copyButton?.addEventListener("click", async () => {
  if (!command || !status) return;
  try {
    await navigator.clipboard.writeText(command.textContent ?? "");
    copyButton.textContent = "Copied ✓";
    status.textContent = "Installation commands copied.";
  } catch {
    status.textContent =
      "Copy unavailable. Select and copy the commands below.";
    copyButton.textContent = "Select commands below";
    const range = document.createRange();
    range.selectNodeContents(command);
    const selection = window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);
  }
});
