import os
import ipaddress
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    database_path: Path = ROOT / "data" / "curriculum.sqlite3"
    read_only_demo: bool = False
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
    max_upload_bytes: int = 10 * 1024 * 1024
    max_package_bytes: int = 32 * 1024 * 1024
    max_results: int = 10_000
    max_topics: int = 100
    web_dist: Path | None = None
    comments_enabled: bool = True
    trusted_proxy_cidrs: tuple[str, ...] = ()
    # Opt-in: allow AI explanations of the bundled synthetic demo on a read-only public stand.
    # Writes (import, save, comments) stay forbidden; AI keeps its demo-only check and rate limits.
    ai_public_demo: bool = False

    @property
    def ai_allowed(self) -> bool:
        return not self.read_only_demo or self.ai_public_demo

    @classmethod
    def from_env(cls):
        flag = os.getenv("READ_ONLY_DEMO", "false").lower()
        if flag not in {"true", "false", "1", "0"}:
            raise ValueError("READ_ONLY_DEMO must be true, false, 1 or 0")
        path = Path(os.getenv("DATABASE_PATH", str(ROOT / "data" / "curriculum.sqlite3")))
        web = os.getenv("WEB_DIST_DIR")
        comments = os.getenv("P1_COMMENTS_ENABLED", "true").lower()
        if comments not in {"true", "false", "1", "0"}:
            raise ValueError("P1_COMMENTS_ENABLED must be true, false, 1 or 0")
        ai_public = os.getenv("AI_PUBLIC_DEMO", "false").lower()
        if ai_public not in {"true", "false", "1", "0"}:
            raise ValueError("AI_PUBLIC_DEMO must be true, false, 1 or 0")
        proxies = tuple(x.strip() for x in os.getenv("TRUSTED_PROXY_CIDRS", "").split(",") if x.strip())
        for cidr in proxies:
            if ipaddress.ip_network(cidr).prefixlen == 0:
                raise ValueError("Trust only verified reverse proxy CIDRs, never all addresses")
        return cls(
            database_path=path if path.is_absolute() else ROOT / path,
            read_only_demo=flag in {"true", "1"},
            cors_origins=tuple(x.strip() for x in os.getenv(
                "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
            ).split(",") if x.strip()),
            web_dist=(Path(web) if Path(web).is_absolute() else ROOT / web) if web else None,
            comments_enabled=comments in {"true", "1"}, trusted_proxy_cidrs=proxies,
            ai_public_demo=ai_public in {"true", "1"},
        )
