"""Bounded, persistent quotas. Forwarding headers are untrusted by default."""
import hashlib
import ipaddress
import math
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass

from backend.app.errors import ApiError


def client_address(scope, trusted_cidrs=()):
    peer = (scope.get("client") or ("unknown", 0))[0]
    networks = [ipaddress.ip_network(cidr) for cidr in trusted_cidrs]

    def address(value):
        parsed = ipaddress.ip_address(value)
        return getattr(parsed, "ipv4_mapped", None) or parsed

    def trusted(value):
        return any(value in network for network in networks)

    try:
        current = address(peer)
        if not trusted(current):
            return str(current)
        headers = [v.decode("ascii") for k, v in scope["headers"] if k.lower() == b"x-forwarded-for"]
        if len(headers) != 1 or len(headers[0]) > 1024:
            return str(current)
        chain = [address(part.strip()) for part in headers[0].split(",")]
        # Walk from the actual TCP peer. Never use the arbitrary leftmost value.
        for hop in reversed(chain):
            if not trusted(current):
                break
            current = hop
        return str(current)
    except (ValueError, UnicodeError):
        return peer


class RateLimited(ApiError):
    def __init__(self, retry_after):
        super().__init__(429, "RATE_LIMITED", "Слишком много запросов. Повторите позже.")
        self.retry_after = max(1, math.ceil(retry_after))

    def response(self, as_csv=False):
        response = super().response(as_csv)
        response.headers["Retry-After"] = str(self.retry_after)
        return response


@dataclass(frozen=True)
class Policy:
    per_ip: int
    per_minute: int
    per_day: int | None = None


POLICIES = {"comments": Policy(10, 60), "ai": Policy(3, 10, 100)}


class RateStore:
    def __init__(self, path, clock=time.time):
        self.path, self.clock = path, clock
        with closing(sqlite3.connect(path, timeout=10)) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS collab_rate_events (
                    id INTEGER PRIMARY KEY, category TEXT NOT NULL,
                    client_key TEXT NOT NULL, created_at REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS collab_rate_time ON collab_rate_events(category, created_at);
                CREATE INDEX IF NOT EXISTS collab_rate_client ON collab_rate_events(category, client_key, created_at);
            """)

    def acquire(self, category, address):
        policy = POLICIES[category]
        now = self.clock()
        key = hashlib.sha256(address.encode("utf-8")).hexdigest()
        denied = None
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM collab_rate_events WHERE (category='comments' AND created_at<=?) OR created_at<=?",
                       (now - 60, now - 86400))
            limits = [(60, policy.per_ip, key), (60, policy.per_minute, None)]
            if policy.per_day:
                limits.append((86400, policy.per_day, None))
            for window, maximum, client in limits:
                sql = "SELECT COUNT(*), MIN(created_at) FROM collab_rate_events WHERE category=? AND created_at>?"
                params = [category, now - window]
                if client is not None:
                    sql += " AND client_key=?"
                    params.append(client)
                count, oldest = db.execute(sql, params).fetchone()
                if count >= maximum:
                    denied = max(denied or 0, oldest + window - now)
            if denied is None:
                db.execute("INSERT INTO collab_rate_events(category,client_key,created_at) VALUES(?,?,?)",
                           (category, key, now))
        if denied is not None:
            raise RateLimited(denied)


class CollabRequestGuard:
    """Enforce limits before JSON parsing, also for chunked/malformed bodies."""
    def __init__(self, app, settings):
        self.app, self.settings = app, settings

    async def __call__(self, scope, receive, send):
        import re
        from starlette.concurrency import run_in_threadpool

        path = scope.get("path", "").rstrip("/")
        match = re.fullmatch(r"/api/datasets/[^/]+/(comments|ai/explain)", path)
        if scope["type"] != "http" or scope.get("method") != "POST" or not match:
            return await self.app(scope, receive, send)
        try:
            category = "comments" if match[1] == "comments" else "ai"
            # Public stand: comments are always read-only; AI only with the explicit AI_PUBLIC_DEMO opt-in.
            if self.settings.read_only_demo and not (category == "ai" and self.settings.ai_allowed):
                raise ApiError(403, "READ_ONLY_DEMO", "Запись и внешние ИИ-запросы отключены в публичном деморежиме.")
            if category == "comments" and not self.settings.comments_enabled:
                raise ApiError(503, "COMMENTS_DISABLED", "Комментарии отключены администратором.")
            # Global quotas bound the number of persisted IP hashes, including failures.
            await run_in_threadpool(scope["app"].state.collab_rates.acquire, category,
                                    client_address(scope, self.settings.trusted_proxy_cidrs))
            limit = 65536
            length = dict(scope["headers"]).get(b"content-length")
            if length is not None:
                try:
                    length = int(length)
                    if length < 0:
                        raise ValueError
                except ValueError:
                    raise ApiError(400, "INVALID_CONTENT_LENGTH", "Некорректный размер запроса.")
                if length > limit:
                    raise ApiError(413, "COLLAB_BODY_TOO_LARGE", "Размер JSON-запроса превышает 64 КиБ.")
            body = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                body.extend(message.get("body", b""))
                if len(body) > limit:
                    raise ApiError(413, "COLLAB_BODY_TOO_LARGE", "Размер JSON-запроса превышает 64 КиБ.")
                if not message.get("more_body", False):
                    break
        except ApiError as exc:
            return await exc.response()(scope, receive, send)
        except sqlite3.OperationalError:
            return await ApiError(503, "DATABASE_UNAVAILABLE", "База временно недоступна. Повторите запрос.").response()(scope, receive, send)
        replayed = False

        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
