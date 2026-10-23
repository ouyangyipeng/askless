import asyncio
import secrets
from collections.abc import AsyncGenerator, Coroutine
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import Field
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.trustedhost import TrustedHostMiddleware

from askless.engine import export_csv
from askless.llm import LLMClient, Settings
from askless.models import Model
from askless.service import Service
from askless.session import Run
from askless.store import Conflict, Store

SAMPLE = """email,name,team
ada@example.com,Ada Lovelace,Research
grace@example.com,Grace Hopper,Engineering
ada@example.com,Ada L.,Systems
lin@example.com,Lin Chen,Research
alan@example.com,Alan Turing,Engineering
lin@example.com,Lin C.,Systems
not-an-email,Needs review,Unknown
,Missing email,Unknown
"""


class CreateRun(Model):
    title: str = Field(min_length=1, max_length=2000)
    csv_text: str = Field(max_length=262_144)
    mode: Literal["live", "offline"] = "live"


class Answers(Model):
    answers: dict[str, str]
    revision: int = Field(ge=0)


def create_app(data_dir: Path | None = None, settings: Settings | None = None) -> FastAPI:
    config = settings or Settings.from_env()
    store = Store((data_dir or Path(".askless")) / "runs.sqlite3")
    service = Service(store, LLMClient(config))
    token = secrets.token_urlsafe(32)
    tasks: set[asyncio.Task[None]] = set()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        store.interrupt_inflight()
        yield
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        store.interrupt_inflight()

    app = FastAPI(title="AskLess", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    def spawn(work: Coroutine[None, None, None]) -> None:
        task = asyncio.create_task(work)
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    @app.middleware("http")
    async def local_boundary(request: Request, call_next: RequestResponseEndpoint) -> Response:
        if (origin := request.headers.get("origin")) and origin != f"{request.url.scheme}://{request.headers.get('host')}":
            return JSONResponse({"detail": "仅允许同源本地请求。"}, status_code=403)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if not secrets.compare_digest(request.headers.get("X-AskLess-Token", ""), token):
                return JSONResponse({"detail": "本机会话凭据失效，请刷新页面。"}, status_code=403)
            if len(await request.body()) > 524_288:
                return JSONResponse({"detail": "请求内容过大。"}, status_code=413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ValueError)
    async def invalid(request: Request, error: ValueError) -> JSONResponse:
        return JSONResponse({"detail": str(error)}, status_code=400)

    @app.exception_handler(Conflict)
    async def conflict(request: Request, error: Conflict) -> JSONResponse:
        return JSONResponse({"detail": str(error)}, status_code=409)

    @app.exception_handler(KeyError)
    async def missing(request: Request, error: KeyError) -> JSONResponse:
        return JSONResponse({"detail": "运行不存在。"}, status_code=404)

    @app.get("/api/config")
    def configuration() -> dict[str, str | bool]:
        return {"token": token, "model": config.model, "configured": bool(config.api_key), "sample_csv": SAMPLE, "version": "0.1.0"}

    @app.get("/api/runs")
    def list_runs() -> list[dict[str, str | int]]:
        return store.list()

    @app.post("/api/runs", status_code=202)
    async def start(body: CreateRun) -> Run:
        run = service.create(body.title, body.csv_text, body.mode)
        spawn(service.prepare(run.id))
        return run

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> Run:
        return store.get(run_id)

    @app.post("/api/runs/{run_id}/answers", status_code=202)
    async def answer(run_id: str, body: Answers) -> Run:
        run = service.answer(run_id, body.answers, body.revision)
        spawn(service.finish(run_id))
        return run

    @app.delete("/api/runs/{run_id}", status_code=204)
    def delete(run_id: str) -> Response:
        store.delete(run_id)
        return Response(status_code=204)

    @app.get("/api/runs/{run_id}/export")
    def export(run_id: str) -> Response:
        run = store.get(run_id)
        if run.status != "completed" or run.result is None or run.result.blocked:
            raise HTTPException(409, "当前运行没有可交付的导入文件。")
        return Response(
            "\ufeff" + export_csv(run.result.rows, run.dataset.columns),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="askless-contacts.csv"'},
        )

    @app.get("/api/runs/{run_id}/evidence")
    def evidence(run_id: str) -> Response:
        return Response(
            store.get(run_id).model_dump_json(indent=2),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="askless-evidence.json"'},
        )

    web = Path(__file__).resolve().parents[2] / "web" / "dist"
    if web.exists():
        app.mount("/assets", StaticFiles(directory=web / "assets"), name="assets")

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(web / "index.html")

    return app
