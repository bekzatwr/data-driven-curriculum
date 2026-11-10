"""Application entry point. Team modules can register APIRouters through create_app."""
import logging
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException

from .api.datasets import router as datasets_router
from .config import Settings
from .db import Store
from .errors import ApiError
from .schemas import Capabilities
from .version import VERSION
from .public_demo import PublicDemoGuard
from planner.api import router as planner_router
from planner.storage import SnapshotStore
from analytics.api import router as analytics_router
from analytics.app import register_analytics_errors
from collab import ai as collab_ai
from collab.api import router as collab_router
from collab.storage import CommentStore

logger = logging.getLogger(__name__)


class ImportBodyLimit:
    """Bound import bodies before multipart/JSON parsing, including chunked requests."""

    def __init__(self, app, settings: Settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST":
            return await self.app(scope, receive, send)
        path = scope["path"].rstrip("/")
        if path not in {"/api/datasets/import", "/api/datasets/restore"}:
            return await self.app(scope, receive, send)
        if self.settings.read_only_demo:
            return await ApiError(403, "READ_ONLY_DEMO", "Импорт отключён в публичном деморежиме.").response()(scope, receive, send)
        # Allow small multipart headers/metadata in addition to the two CSV files.
        limit = (self.settings.max_package_bytes if path.endswith("/restore")
                 else self.settings.max_upload_bytes + 64 * 1024)
        length = dict(scope["headers"]).get(b"content-length")
        if length is not None:
            try:
                length = int(length)
                if length < 0:
                    raise ValueError
            except ValueError:
                return await ApiError(400, "INVALID_CONTENT_LENGTH", "Некорректный размер запроса.").response()(scope, receive, send)
            if length > limit:
                return await ApiError(413, "UPLOAD_TOO_LARGE", "Запрос превышает допустимый размер.").response()(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > limit:
                return await ApiError(413, "UPLOAD_TOO_LARGE", "Запрос превышает допустимый размер.").response()(scope, receive, send)
            if not message.get("more_body", False):
                break
        replayed = False

        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


def create_app(settings: Settings | None = None, routers: tuple[APIRouter, ...] = ()) -> FastAPI:
    settings = settings or Settings.from_env()
    store = Store(settings.database_path, demo_only=settings.read_only_demo)

    @asynccontextmanager
    async def lifespan(application):
        await run_in_threadpool(store.initialize)
        # Keep source data and Aidana's immutable snapshots in the same backup/volume.
        application.state.plan_snapshots = await run_in_threadpool(SnapshotStore, settings.database_path)
        if settings.read_only_demo:
            # Seed trusted bundled fixtures before accepting public HTTP requests.
            from analytics.demo import demo_files
            from .validation import validate_upload
            upload = await run_in_threadpool(validate_upload, *demo_files(), settings, source_type="demo")
            dataset, _ = await run_in_threadpool(store.save_upload, upload)
            application.state.public_demo = (upload, dataset)
        # P1: comments live in the same database file, so backups and restarts keep them.
        application.state.comments = await run_in_threadpool(CommentStore, settings.database_path)
        yield

    application = FastAPI(
        title="Data-Driven Curriculum — backend", version=VERSION, lifespan=lifespan,
        description="Импорт, аналитика тем, сравнение учебников, планирование часов и сохранённые отчёты.",
    )
    application.state.settings = settings
    application.state.store = store
    application.add_middleware(ImportBodyLimit, settings=settings)
    application.add_middleware(PublicDemoGuard, settings=settings)
    application.add_middleware(
        CORSMiddleware, allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type"],
        expose_headers=["Content-Disposition"],
    )

    @application.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError):
        return exc.response()

    @application.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        details = [{"file": "request", "row": None,
                    "field": ".".join(str(x) for x in e["loc"]), "reason": e["msg"]}
                   for e in exc.errors()]
        return ApiError(422, "INVALID_REQUEST", "Проверьте параметры запроса.", details).response()

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        response = ApiError(exc.status_code, f"HTTP_{exc.status_code}", str(exc.detail)).response()
        response.headers.update(exc.headers or {})
        return response

    @application.exception_handler(sqlite3.OperationalError)
    async def database_error(request: Request, exc: sqlite3.OperationalError):
        logger.exception("Database operation failed")
        return ApiError(503, "DATABASE_UNAVAILABLE", "База временно недоступна. Повторите запрос.").response()

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        logger.exception("Unhandled server error")
        return ApiError(500, "INTERNAL_ERROR", "Внутренняя ошибка сервера.").response()

    @application.get("/api/health", tags=["System"])
    def health():
        if not store.ping():
            raise ApiError(503, "DATABASE_UNAVAILABLE", "База данных недоступна.")
        return {"status": "ok", "version": VERSION, "database": "ok", "read_only_demo": settings.read_only_demo}

    @application.get("/api/capabilities", response_model=Capabilities, tags=["System"])
    def capabilities():
        return {
            "version": VERSION, "mode": "read_only_demo" if settings.read_only_demo else "local",
            "limits": {"csv_files_bytes": settings.max_upload_bytes,
                       "multipart_body_bytes": settings.max_upload_bytes + 64 * 1024,
                       "package_body_bytes": settings.max_package_bytes,
                       "results_per_dataset": settings.max_results, "topics_per_dataset": settings.max_topics,
                       "results_per_page": 1000},
            "features": {"csv_import": not settings.read_only_demo, "import_preview": not settings.read_only_demo,
                         "demo_dataset": True, "data_quality": True, "package_export": True,
                         "package_restore": not settings.read_only_demo,
                         "plan_preview": True, "plan_save": not settings.read_only_demo, "plan_report": True, "plan_csv": True,
                         "analytics": True, "textbook_comparison": True,
                         "comments": True, "ai_explain": collab_ai.status()["configured"]},
            "links": {"docs": "/docs", "openapi": "/openapi.json", "datasets": "/api/datasets",
                      "results_template": "/api/templates/results.csv",
                      "curriculum_template": "/api/templates/curriculum.csv"},
        }

    application.include_router(datasets_router)
    application.include_router(planner_router)
    application.include_router(analytics_router)
    application.include_router(collab_router)
    register_analytics_errors(application)
    for router in routers:
        if router not in (planner_router, analytics_router, collab_router):
            application.include_router(router)

    if settings.web_dist:
        dist = Path(settings.web_dist).resolve()
        if not (dist / "index.html").is_file():
            raise ValueError("WEB_DIST_DIR must contain Damir's built index.html")

        @application.get("/{path:path}", include_in_schema=False)
        def web(path: str):
            if path.split("/", 1)[0] in {"api", "docs", "redoc", "openapi.json"}:
                raise ApiError(404, "HTTP_404", "Not Found")
            target = (dist / path).resolve()
            if not target.is_relative_to(dist):
                raise ApiError(404, "HTTP_404", "Not Found")
            if target.is_file():
                return FileResponse(target)
            if Path(path).suffix:
                raise ApiError(404, "HTTP_404", "Not Found")
            return FileResponse(dist / "index.html")
    else:
        @application.get("/", include_in_schema=False)
        def root():
            return {"service": "Data-Driven Curriculum API", "docs": "/docs", "health": "/api/health"}

    return application


app = create_app()
