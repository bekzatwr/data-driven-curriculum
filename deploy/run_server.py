"""Container entry point: validate the mount/port, then replace PID 1 with Uvicorn."""
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def flag(name):
    value = os.getenv(name, "false").lower()
    if value not in {"true", "false", "1", "0"}:
        raise ValueError(name + " must be true, false, 1 or 0")
    return value in {"true", "1"}


def preflight():
    from backend.app.config import Settings

    port = int(os.getenv("PORT", "8000"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be between 1 and 65535")
    settings = Settings.from_env()
    if flag("PUBLIC_DEMO") and not settings.read_only_demo:
        raise ValueError("PUBLIC_DEMO requires READ_ONLY_DEMO=true; refusing public writes")
    database = settings.database_path.resolve()
    if flag("REQUIRE_PERSISTENT_STORAGE"):
        mount = Path(os.getenv("DATA_MOUNT_PATH", "/app/data")).resolve()
        if not mount.is_mount() or not database.is_relative_to(mount):
            raise ValueError("DATABASE_PATH must be inside the mounted DATA_MOUNT_PATH; refusing ephemeral storage")
    database.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryFile(dir=database.parent):
        pass
    if flag("REQUIRE_P0"):
        if not settings.web_dist or not (settings.web_dist / "index.html").is_file():
            raise ValueError("P0 blocked: Damir's built frontend is missing")
        from backend.app.main import app
        required = {
            "/api/datasets/{dataset_id}/overview",
            "/api/datasets/{dataset_id}/topics/{topic_id}",
            "/api/datasets/{dataset_id}/comparison",
        }
        paths = app.openapi()["paths"]
        missing = {path for path in required if "get" not in paths.get(path, {})}
        if missing:
            raise ValueError("P0 blocked: missing analytics routes: " + ", ".join(sorted(missing)))
    return port


if __name__ == "__main__":
    try:
        port = preflight()
    except (ValueError, OSError) as exc:
        sys.exit(f"Deployment preflight failed: {exc}")
    os.execvp(sys.executable, [sys.executable, "-m", "uvicorn", "backend.app.main:app",
                              "--host", "0.0.0.0", "--port", str(port), "--workers", "1",
                              "--no-proxy-headers",
                              "--timeout-graceful-shutdown", "25"])
