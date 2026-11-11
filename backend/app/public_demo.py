"""HTTP write policy for the public synthetic-data demonstration."""
import re

from .errors import ApiError


class PublicDemoGuard:
    """Reject writes before parsing bodies; preview and demo lookup are read-only."""

    def __init__(self, app, settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and self.settings.read_only_demo:
            path = scope["path"].rstrip("/")
            method = scope["method"]
            allowed_post = method == "POST" and (
                path == "/api/datasets/demo"
                or re.fullmatch(r"/api/datasets/[^/]+/plans/preview", path)
                # AI_PUBLIC_DEMO opt-in: explanations only; collab guard keeps quotas and demo-only checks.
                or (self.settings.ai_public_demo and re.fullmatch(r"/api/datasets/[^/]+/ai/explain", path))
            )
            if path.startswith("/api/") and method not in {"GET", "HEAD", "OPTIONS"} and not allowed_post:
                response = ApiError(403, "READ_ONLY_DEMO",
                                    "Публичный демостенд доступен только для просмотра и расчёта. "
                                    "Импорт и сохранение выполняются на локальном стенде команды.").response()
                return await response(scope, receive, send)
        return await self.app(scope, receive, send)
