import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import DecisionWorkbench from "./DecisionWorkbench";
import "./style.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {window.location.pathname === "/decisions" ? (
      <DecisionWorkbench />
    ) : (
      <App />
    )}
  </React.StrictMode>,
);
