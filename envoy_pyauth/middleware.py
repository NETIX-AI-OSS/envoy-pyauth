import base64
import binascii
import hashlib
import json
import logging
import os
import time
from typing import Any

import requests
from django.core.cache import cache
from django.http import HttpResponseBase
from django.utils.deprecation import MiddlewareMixin

from .types import EnvoyHttpRequest

logger = logging.getLogger(__name__)

_AUTH_TIMEOUT = float(os.environ.get("ENVOY_AUTH_TIMEOUT", "10"))
_CACHE_TTL = int(os.environ.get("ENVOY_AUTH_CACHE_TTL", "300"))
# Security changes (account disable, org/permission changes, credential revocation)
# must converge quickly even if a consumer asks for a much longer cache lifetime.
_MAX_CACHE_TTL = 30


class AuthorizationMiddleware(MiddlewareMixin):
    """Resolve the incoming Authorization header to an envoy payload on ``request.envoy``.

    Supported schemes (in this order):

    * ``Bearer <jwt|hs_auth_token>`` and session cookies — forwarded to
      ``/auth/me/`` directly.
    * ``api <raw_haystack_key>`` — exchanged via
      ``POST /auth/scram/api-key-login/`` for a Bearer authToken, then resolved
      against ``/auth/me/``. This is the Haystack 4 service-to-service path.

    Only the inbound ``Authorization`` header is considered. Service credentials
    remain available to outbound clients through their explicit environment
    variables, but are never substituted for a missing caller credential.

    On any failure ``request.envoy`` is set to ``None``. Positive results are
    cached under a SHA-256 of the raw header for at most 30 seconds, and never
    beyond a JWT's ``exp`` claim.
    """

    def process_view(
        self,
        request: EnvoyHttpRequest,
        view_func: Any,
        *view_args: Any,
        **view_kwargs: Any,
    ) -> HttpResponseBase | None:
        if getattr(view_func, "_envoy_auth_exempt", False) or getattr(
            getattr(view_func, "cls", None), "_envoy_auth_exempt", False
        ):
            request.envoy = None
            return None
        try:
            auth_header = request.META.get("HTTP_AUTHORIZATION")
            request.envoy = _resolve(auth_header) if auth_header else None
        # Cache backends and integrations can raise implementation-specific errors.
        # The security invariant is to clear identity on every unexpected failure.
        except Exception as exc:  # noqa: BLE001  # pragma: no cover - defensive
            logger.warning("envoy_pyauth: %s", exc)
            request.envoy = None
        return None


def _resolve(auth_header: str) -> dict[str, Any] | None:
    cache_key = _cache_key(auth_header)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    payload = _fetch_me(auth_header)
    if payload is None and auth_header.lower().startswith("api "):
        raw_key = auth_header.split(None, 1)[1].strip()
        if raw_key:
            bearer = _exchange_haystack_key(raw_key)
            if bearer:
                payload = _fetch_me(f"Bearer {bearer}")

    if payload is not None:
        timeout = _cache_timeout(auth_header)
        if timeout > 0:
            cache.set(cache_key, payload, timeout=timeout)
    return payload


def _cache_key(auth_header: str) -> str:
    digest = hashlib.sha256(auth_header.encode("utf-8")).hexdigest()
    return f"envoy_pyauth:auth:v2:{digest}"


def _cache_timeout(auth_header: str) -> int:
    timeout = max(0, min(_CACHE_TTL, _MAX_CACHE_TTL))
    if timeout == 0 or not auth_header.lower().startswith("bearer "):
        return timeout
    token = auth_header.split(None, 1)[1].strip()
    parts = token.split(".")
    if len(parts) != 3:
        return timeout
    try:
        segment = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(segment).decode("utf-8"))
        expires_at = float(claims["exp"])
    except binascii.Error, KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError:
        return timeout
    return max(0, min(timeout, int(expires_at - time.time())))


def _identity_payload(value: Any) -> dict[str, Any] | None:
    """Validate the minimum ``/auth/me/`` contract before trusting or caching it."""
    if not isinstance(value, dict):
        return None
    organization = value.get("organization")
    permissions = value.get("permissions")
    if organization in (None, "", "bogus") or not isinstance(permissions, (list, tuple, set, frozenset)):
        return None
    payload = dict(value)
    payload["permissions"] = list(permissions)
    return payload


def _fetch_me(auth_header: str) -> dict[str, Any] | None:
    url = _auth_svc_url() + "/auth/me/"
    try:
        resp = requests.get(url, headers={"Authorization": auth_header}, timeout=_AUTH_TIMEOUT)
    except requests.RequestException as exc:
        logger.warning("envoy_pyauth: /auth/me/ unreachable: %s", exc)
        return None
    if resp.status_code == 200:
        try:
            return _identity_payload(resp.json())
        except requests.exceptions.JSONDecodeError:
            logger.warning("envoy_pyauth: /auth/me/ returned invalid JSON")
            return None
    logger.debug("envoy_pyauth: /auth/me/ returned %s", resp.status_code)
    return None


def _exchange_haystack_key(raw_key: str) -> str | None:
    url = _auth_svc_url() + "/auth/scram/api-key-login/"
    try:
        resp = requests.post(url, json={"apiKey": raw_key}, timeout=_AUTH_TIMEOUT)
    except requests.RequestException as exc:
        logger.warning("envoy_pyauth: api-key-login unreachable: %s", exc)
        return None
    if resp.status_code == 200:
        token = resp.json().get("authToken")
        return str(token) if token is not None else None
    logger.debug("envoy_pyauth: api-key-login returned %s", resp.status_code)
    return None


def _auth_svc_url() -> str:
    return os.getenv("USER_AUTH_SVC_URL", "http://user-management-auth.backend:8001")
