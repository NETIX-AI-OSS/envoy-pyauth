from types import SimpleNamespace

from envoy_pyauth.decorator import envoy_internal_only, envoy_permission


def _request(identity):
    return SimpleNamespace(envoy=identity)


def test_envoy_permission_supports_function_and_method_views():
    @envoy_permission("asset-edit")
    def function_view(request):
        return "function-ok"

    class View:
        @envoy_permission("asset-edit")
        def method_view(self, request):
            return "method-ok"

    identity = {"permissions": ["asset-edit"], "organization": 7}
    assert function_view(_request(identity)) == "function-ok"
    assert View().method_view(_request(identity)) == "method-ok"
    assert function_view.__name__ == "function_view"


def test_envoy_permission_fails_closed_without_identity_or_required_permission(monkeypatch):
    @envoy_permission("asset-edit")
    def view(request):
        return "should-not-run"

    monkeypatch.setenv("DJANGO_DEBUG", "TRUE")
    assert view(_request(None)).status_code == 401
    assert view(_request({"permissions": [], "organization": 7})).status_code == 403
    assert view(_request({"permissions": "asset-edit", "organization": 7})).status_code == 401
    assert view(_request({"permissions": ["asset-edit"]})).status_code == 401


def test_internal_only_requires_explicit_platform_identity():
    @envoy_internal_only()
    def view(request):
        return "ok"

    assert view(_request(None)).status_code == 401
    assert view(_request({"user_type": "organization", "organization": 7, "permissions": []})).status_code == 403


def test_internal_only_accepts_explicit_and_legacy_platform_identity():
    @envoy_internal_only()
    def view(request):
        return "ok"

    assert view(_request({"is_platform_internal": True, "organization": 0, "permissions": []})) == "ok"
    legacy = {
        "username": "platform_internal",
        "user_id": 0,
        "organization": 0,
        "is_superuser": True,
        "permissions": [],
    }
    assert view(_request(legacy)) == "ok"


def test_internal_only_named_services_are_opt_in():
    @envoy_internal_only(allowed_services=("tag-service",))
    def view(*, request):
        return "ok"

    tag = {"user_type": "service", "service_name": "tag-service", "organization": 7, "permissions": []}
    other = {"user_type": "service", "service_name": "other-service", "organization": 7, "permissions": []}
    assert view(request=_request(tag)) == "ok"
    assert view(request=_request(other)).status_code == 403
