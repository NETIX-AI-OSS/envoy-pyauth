# envoy-pyauth

`envoy-pyauth` is a lightweight Django/DRF integration library for Envoy-style
authentication context propagation, permission checks, and organization-scoped
query filtering.

## Installation

```bash
pip install envoy-pyauth
```

Or from local source:

```bash
pip install -e .
```

## Quickstart

### 1) Register middleware

Add the middleware to your Django settings:

```python
MIDDLEWARE = [
    # ...
    "envoy_pyauth.middleware.AuthorizationMiddleware",
    # ...
]
```

### 2) Protect DRF view methods with permissions

```python
from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from envoy_pyauth.decorator import envoy_permission


class ProjectViewSet(ViewSet):
    @envoy_permission("projects.read")
    def list(self, request):
        return Response({"ok": True})
```

### 3) Use organization-scoped queryset filtering

```python
from envoy_pyauth.utils import EnvoyQueryFilter


queryset = EnvoyQueryFilter.filter_queryset(
    request=request,
    queryset=Project.objects.all(),
    session_customer_filter=True,
    field_name="organization_id",
    delete_filter=True,
)
```

## Documentation

- [Documentation Home](docs/index.md)
- [Use Cases](docs/use-cases.md)
- [Architecture](docs/architecture.md)
- [Patterns](docs/patterns.md)
- [API Reference](docs/reference.md)

## Behavior Notes

- Authentication and authorization remain fail-closed when `DJANGO_DEBUG == "TRUE"`.
  Local tests must attach an explicit `request.envoy` identity or mark a genuinely
  public view with `@envoy_auth_exempt`.
- Missing or malformed identity never produces an unscoped tenant query.
- `@envoy_internal_only()` requires a resolved platform-internal identity. Named
  service identities must be explicitly allow-listed by the endpoint.
- The library relies on an external auth service (`USER_AUTH_SVC_URL`) for
  identity context resolution.
- Positive identities are cached for at most 30 seconds, shortened further by a
  JWT `exp` claim. Longer `ENVOY_AUTH_CACHE_TTL` values are safely capped.

## Environment Variables

- `DJANGO_DEBUG` (optional compatibility setting; never bypasses authorization)
- `USER_AUTH_SVC_URL` (optional, default:
  `http://user-management-auth.backend:8001`)
- `ENVOY_AUTH_CACHE_TTL` (optional; hard-capped at 30 seconds)

`USER_SVC_AUTH` remains an outbound service-client credential. It is deliberately
not used as a fallback for an inbound request that lacks `Authorization`.

## Upgrading to 2.0

- Tests and local clients must send an `Authorization` header or attach a complete
  `request.envoy` envelope; `DJANGO_DEBUG` no longer grants access.
- Service-to-service clients may keep reading `USER_SVC_AUTH` or a service-specific
  variable, but must put that value in the outbound `Authorization` header.
- Existing platform-internal credentials remain compatible with
  `@envoy_internal_only()`. New named service identities require an explicit
  `allowed_services=(...)` declaration.
- Code that deliberately disables tenant filtering must still supply a resolved
  identity. Unknown object ownership is now denied for writes.

## License

AGPL-3.0-only. See [LICENSE](LICENSE).
