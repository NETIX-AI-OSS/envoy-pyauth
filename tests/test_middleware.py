import base64
import json
from types import SimpleNamespace

from envoy_pyauth import middleware


class DummyCache:
    def __init__(self, value=None):
        self.value = value
        self.set_calls = []

    def get(self, key):
        return self.value

    def set(self, key, value, timeout):
        self.set_calls.append((key, value, timeout))


def _jwt(payload):
    segment = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"header.{segment}.signature"


def test_process_view_uses_only_inbound_authorization(monkeypatch):
    resolved = []
    monkeypatch.setenv("USER_SVC_AUTH", "Bearer shared-service-secret")
    monkeypatch.setattr(middleware, "_resolve", lambda header: resolved.append(header) or {"organization": 7})
    auth = middleware.AuthorizationMiddleware(lambda request: None)

    missing = SimpleNamespace(META={})
    auth.process_view(missing, lambda request: None)
    assert missing.envoy is None
    assert resolved == []

    inbound = SimpleNamespace(META={"HTTP_AUTHORIZATION": "Bearer caller"})
    auth.process_view(inbound, lambda request: None)
    assert inbound.envoy == {"organization": 7}
    assert resolved == ["Bearer caller"]


def test_process_view_never_uses_debug_identity(monkeypatch):
    monkeypatch.setenv("DJANGO_DEBUG", "TRUE")
    request = SimpleNamespace(META={})
    middleware.AuthorizationMiddleware(lambda req: None).process_view(request, lambda req: None)
    assert request.envoy is None


def test_resolve_caps_cache_at_thirty_seconds(monkeypatch):
    cache = DummyCache()
    payload = {"organization": 7, "permissions": ["asset-view"]}
    monkeypatch.setattr(middleware, "cache", cache)
    monkeypatch.setattr(middleware, "_CACHE_TTL", 3600)
    monkeypatch.setattr(middleware, "_fetch_me", lambda header: payload)

    assert middleware._resolve("Bearer opaque-token") == payload
    assert cache.set_calls[0][2] == 30


def test_cache_timeout_is_shortened_by_jwt_expiry(monkeypatch):
    monkeypatch.setattr(middleware, "_CACHE_TTL", 300)
    monkeypatch.setattr(middleware.time, "time", lambda: 1000)
    assert middleware._cache_timeout(f"Bearer {_jwt({'exp': 1012})}") == 12
    assert middleware._cache_timeout(f"Bearer {_jwt({'exp': 999})}") == 0
    assert middleware._cache_timeout("Bearer not-a-jwt") == 30


def test_fetch_me_rejects_malformed_identity(monkeypatch):
    class Response:
        status_code = 200

        def __init__(self, data):
            self.data = data

        def json(self):
            return self.data

    monkeypatch.setattr(middleware.requests, "get", lambda *args, **kwargs: Response({"permissions": []}))
    assert middleware._fetch_me("Bearer token") is None

    expected = {"organization": "7", "permissions": ("asset-view",)}
    monkeypatch.setattr(middleware.requests, "get", lambda *args, **kwargs: Response(expected))
    assert middleware._fetch_me("Bearer token") == {"organization": "7", "permissions": ["asset-view"]}


def test_api_key_exchange_is_cached_under_original_credential(monkeypatch):
    cache = DummyCache()
    calls = []
    monkeypatch.setattr(middleware, "cache", cache)
    monkeypatch.setattr(middleware, "_exchange_haystack_key", lambda raw: "exchanged")

    def fetch(header):
        calls.append(header)
        if header == "Bearer exchanged":
            return {"organization": 9, "permissions": ["read"]}
        return None

    monkeypatch.setattr(middleware, "_fetch_me", fetch)
    result = middleware._resolve("api raw-key")
    assert result == {"organization": 9, "permissions": ["read"]}
    assert calls == ["api raw-key", "Bearer exchanged"]
    assert cache.set_calls[0][0] == middleware._cache_key("api raw-key")
