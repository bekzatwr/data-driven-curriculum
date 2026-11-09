import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    database_path: Path = ROOT / "data" / "curriculum.sqlite3"
    read_only_demo: bool = False
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
    max_upload_bytes: int = 10 * 1024 * 1024
    max_results: int = 10_000
    max_topics: int = 100
    web_dist: Path | None = None

    @classmethod
    def from_env(cls):
        flag = os.getenv("READ_ONLY_DEMO", "false").lower()
        if flag not in {"true", "false", "1", "0"}:
            raise ValueError("READ_ONLY_DEMO must be true, false, 1 or 0")
        path = Path(os.getenv("DATABASE_PATH", str(ROOT / "data" / "curriculum.sqlite3")))
        web = os.getenv("WEB_DIST_DIR")
        return cls(
            database_path=path if path.is_absolute() else ROOT / path,
            read_only_demo=flag in {"true", "1"},
            cors_origins=tuple(x.strip() for x in os.getenv(
                "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
            ).split(",") if x.strip()),
            web_dist=(Path(web) if Path(web).is_absolute() else ROOT / web) if web else None,
        )
