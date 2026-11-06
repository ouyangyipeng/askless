"""A stdio MCP adapter bound to one explicitly selected local input file."""

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import JsonValue

from askless.decision_models import DecisionRun
from askless.decision_sessions import DecisionSessions
from askless.exporter import read_records
from askless.store import Conflict


def local_web_url(value: str) -> str:
    url = urlsplit(value)
    if (
        url.scheme not in {"http", "https"}
        or url.hostname not in {"127.0.0.1", "localhost"}
        or url.username
        or url.password
        or url.query
        or url.fragment
        or url.path not in {"", "/"}
    ):
        raise ValueError("Workbench URL must be a local HTTP(S) origin.")
    return value.rstrip("/")


def session_summary(sessions: DecisionSessions, run: DecisionRun, web_url: str) -> dict[str, JsonValue]:
    view = sessions.view(run.id)
    groups = view["decisions"]
    assert isinstance(groups, list)
    summary: dict[str, JsonValue] = {
        "session_id": run.id,
        "status": run.status,
        "revision": run.revision,
        "preview_url": f"{web_url}/decisions?session={run.id}",
        "pending": view["pending"],
        "answers": dict(run.answers),
        "auto_resolved": [g["key"] for g in groups if isinstance(g, dict) and g["status"] == "auto"],
        "preview_calls": len(run.snapshot.trials) if run.snapshot else len(run.partial_trials),
        "error": run.error,
    }
    if run.result:
        artifact = sessions.artifact(run.id)
        summary["artifact"] = {
            "name": artifact.name,
            "bytes": artifact.bytes,
            "output_hash": run.result.output_hash,
            "download_url": f"{web_url}/api/decisions/{run.id}/artifact",
        }
    return summary


def _call(action: Callable[[], dict[str, JsonValue]]) -> dict[str, JsonValue]:
    try:
        return action()
    except (ValueError, Conflict) as error:
        raise ToolError(str(error)) from None
    except (OSError, KeyError):
        raise ToolError("The selected input or session is unavailable.") from None
    except Exception:  # noqa: BLE001 -- Tool errors must not expose arbitrary exception data.
        raise ToolError("The local preview could not be completed.") from None


def create_server(source: Path, data_dir: Path, web_url: str = "http://127.0.0.1:8765") -> MCPServer:
    path, web = source.resolve(), local_web_url(web_url)
    sessions = DecisionSessions(data_dir / "decisions.sqlite3")
    server = MCPServer(
        "AskLess",
        instructions="Preview the selected file, let the user choose in the workbench, then collect the verified artifact. Tools never choose answers on the user's behalf.",
    )

    def owned(session_id: str) -> DecisionRun:
        run = sessions.get(session_id)
        if run.owner != "mcp" or run.source_path != str(path):
            raise Conflict("Session is outside this server's selected input scope.")
        return run

    @server.tool(name="preview_export")
    def prepare(title: str, request_id: str) -> dict[str, JsonValue]:
        """Preview JSON/CSV export of the configured file. Returns a persistent decision URL; no raw rows are returned."""
        return _call(lambda: session_summary(sessions, sessions.create(title, read_records(path), request_id, source_path=path, owner="mcp"), web))

    @server.tool(name="inspect_session")
    def inspect(session_id: str) -> dict[str, JsonValue]:
        """Read the status, pending decisions and confirmed answers for this input. Does not answer or complete a session."""
        return _call(lambda: session_summary(sessions, owned(session_id), web))

    @server.tool(name="collect_export")
    def collect(session_id: str, revision: int) -> dict[str, JsonValue]:
        """After human choices are complete, verify the current input and replay the policy. Returns artifact metadata and a local download URL."""

        def finish() -> dict[str, JsonValue]:
            owned(session_id)
            return session_summary(sessions, sessions.complete(session_id, revision), web)

        return _call(finish)

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="AskLess stdio MCP server for one local file")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=Path(".askless"))
    parser.add_argument("--web-url", default="http://127.0.0.1:8765")
    args = parser.parse_args()
    server = create_server(cast(Path, args.input), cast(Path, args.data_dir), args.web_url)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
