from typing import Any

from django.http import HttpRequest


class EnvoyHttpRequest(HttpRequest):
    """HttpRequest with envoy payload attached by AuthorizationMiddleware."""

    envoy: dict[str, Any] | None
