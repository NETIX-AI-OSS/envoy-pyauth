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

- This library intentionally supports debug-oriented flows controlled by
  `DJANGO_DEBUG == "TRUE"` to simplify integration debugging.
- Runtime behavior is intentionally documented as current implementation behavior
  and is not hardened by this documentation change.
- The library relies on an external auth service (`USER_AUTH_SVC_URL`) for
  identity context resolution.

## Environment Variables

- `DJANGO_DEBUG` (required by current implementation)
- `USER_AUTH_SVC_URL` (optional, default:
  `http://user-management-auth.backend:8001`)
- `USER_SVC_AUTH` (optional fallback auth header value)

## License

AGPL-3.0-only. See [LICENSE](LICENSE).
