import hashlib
import logging
import os

import requests
from django.core.cache import cache
from django.utils.deprecation import MiddlewareMixin

from .common import DJANGO_DEBUG

logger = logging.getLogger(__name__)

_AUTH_TIMEOUT = float(os.environ.get("ENVOY_AUTH_TIMEOUT", "10"))
_CACHE_TTL = int(os.environ.get("ENVOY_AUTH_CACHE_TTL", "300"))

_DEBUG_PAYLOAD = {
    "username": "DEBUG",
    "is_superuser": "true",
    "user_type": "organization",
    "organization": 0,
    "site_id": None,
    "permissions": ["sample-permission"],
    "groups": ["groups"],
    "feature_flags": "feature_1",
}


class AuthorizationMiddleware(MiddlewareMixin):
    """Resolve the incoming Authorization header to an envoy payload on ``request.envoy``.

    Supported schemes (in this order):

    * ``Bearer <jwt|hs_auth_token>`` and session cookies — forwarded to
      ``/auth/me/`` directly.
    * ``api <raw_haystack_key>`` — exchanged via
      ``POST /auth/scram/api-key-login/`` for a Bearer authToken, then resolved
      against ``/auth/me/``. This is the Haystack 4 service-to-service path.

    On any failure ``request.envoy`` is set to ``None`` (consistent with prior
    behavior). Positive results are cached in Django's cache backend, keyed by
    a SHA-256 of the raw header, for ``ENVOY_AUTH_CACHE_TTL`` seconds (default
    300) so a single tag-service ↔ asset-service hop doesn't trigger 3 HTTP
    calls back to user-management on every request.
    """

    def process_view(self, request, view_func, *view_args, **view_kwargs):
        if getattr(view_func, "_envoy_auth_exempt", False) or getattr(
            getattr(view_func, "cls", None), "_envoy_auth_exempt", False
        ):
            request.envoy = None
            return None
        if DJANGO_DEBUG:
            request.envoy = _DEBUG_PAYLOAD
            return None
        try:
            auth_header = request.META.get("HTTP_AUTHORIZATION") or os.getenv("USER_SVC_AUTH")
            request.envoy = _resolve(auth_header) if auth_header else None
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("envoy_pyauth: %s", exc)
            request.envoy = None
        return None


def _resolve(auth_header):
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
        cache.set(cache_key, payload, timeout=_CACHE_TTL)
    return payload


def _cache_key(auth_header):
    digest = hashlib.sha256(auth_header.encode("utf-8")).hexdigest()
    return f"envoy_pyauth:auth:{digest}"


def _fetch_me(auth_header):
    url = _auth_svc_url() + "/auth/me/"
    try:
        resp = requests.get(url, headers={"Authorization": auth_header}, timeout=_AUTH_TIMEOUT)
    except requests.RequestException as exc:
        logger.warning("envoy_pyauth: /auth/me/ unreachable: %s", exc)
        return None
    if resp.status_code == 200:
        return resp.json()
    logger.debug("envoy_pyauth: /auth/me/ returned %s", resp.status_code)
    return None


def _exchange_haystack_key(raw_key):
    url = _auth_svc_url() + "/auth/scram/api-key-login/"
    try:
        resp = requests.post(url, json={"apiKey": raw_key}, timeout=_AUTH_TIMEOUT)
    except requests.RequestException as exc:
        logger.warning("envoy_pyauth: api-key-login unreachable: %s", exc)
        return None
    if resp.status_code == 200:
        return resp.json().get("authToken")
    logger.debug("envoy_pyauth: api-key-login returned %s", resp.status_code)
    return None


def _auth_svc_url():
    return os.getenv("USER_AUTH_SVC_URL", "http://user-management-auth.backend:8001")
