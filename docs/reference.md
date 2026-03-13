# API Reference

This reference documents current behavior of public utilities in `envoy-pyauth`.

## Module: `envoy_pyauth.middleware`

### `class AuthorizationMiddleware(MiddlewareMixin)`

#### `process_view(self, request, view_func, *view_args, **view_kwargs)`

Purpose:

- Resolves auth token.
- Calls external auth service (`/auth/me/`).
- Attaches parsed payload to `request.envoy`.

Token resolution order:

1. `request.META.get("HTTP_AUTHORIZATION")`
2. `os.getenv("USER_SVC_AUTH")`

Auth URL behavior:

- Base from `USER_AUTH_SVC_URL`.
- Default base: `http://user-management-auth.backend:8001`.
- Effective endpoint: `<base>/auth/me/`.

Assignment behavior:

- On success: `request.envoy = api_response.json()`.
- On request errors: warning log, then `request.envoy = None`.
- On outer exception: warning log and returns `None`.

Debug behavior:

- If `DJANGO_DEBUG` is true, middleware first populates a debug payload in `request.envoy`.
- Middleware still proceeds with token resolution and external call path afterward.

Debug payload shape used by current implementation:

```json
{
  "username": "DEBUG",
  "is_superuser": "true",
  "user_type": "organization",
  "organization": 0,
  "site_id": null,
  "permissions": ["sample-permission"],
  "groups": ["groups"],
  "feature_flags": "feature_1"
}
```

## Module: `envoy_pyauth.decorator`

### `envoy_permission(permission_name)`

Returns a decorator that wraps a view function.

Behavior:

- If `DJANGO_DEBUG` is true: executes wrapped function directly.
- Otherwise:
  - Reads `request` from `args[1]`.
  - Checks membership: `permission_name in request.envoy["permissions"]`.
  - If missing: returns DRF `Response(status=403)`.
  - On exception (missing keys/shape/etc.): logs warning and returns `Response(status=400)`.

Usage note:

- This wrapper assumes DRF-style method signatures where `request` is positional argument 2.

### `envoy_internal_only()`

Returns a decorator that wraps a view function.

Behavior:

- If `DJANGO_DEBUG` is true: executes wrapped function directly.
- Otherwise:
  - Reads `request` from `args[1]`.
  - If `getattr(request, "envoy", False)` is truthy: returns `Response(status=403)`.
  - On exception: logs warning and returns `Response(status=400)`.
  - Else executes wrapped function.

## Module: `envoy_pyauth.utils`

### `class EnvoyQueryFilter`

#### `get_queryset(request, model, session_customer_filter, field_name="organization_id", delete_filter=True)`

Returns a model queryset filtered according to request/envoy context.

Fallback branch (returns broad/default query) when any is true:

- `request is None`
- `not session_customer_filter`
- `not getattr(request, "envoy", False)`
- `request.envoy["organization"] == 0`

Fallback results:

- If `delete_filter=True`: `model.objects.filter(is_deleted=False).order_by("id")`
- Else: `model.objects.all()`

Scoped branch:

- Filters on `field_name__in=[0, request.envoy["organization"]]`
- Applies `is_deleted=False` when `delete_filter=True`
- Orders by `id` in delete-filter branch

Exception behavior:

- On `KeyError` while reading envoy organization: returns `model.objects.none()`.

#### `filter_queryset(request, queryset, session_customer_filter, field_name="organization_id", delete_filter=True)`

Same branching behavior as `get_queryset`, but operates on an existing queryset instance.

## Module: `envoy_pyauth.common`

### `DJANGO_DEBUG`

Definition:

- `DJANGO_DEBUG = os.environ["DJANGO_DEBUG"] == "TRUE"`

Implication:

- Environment variable must exist at import time in current implementation.

## Import surface

The package module `envoy_pyauth/__init__.py` is currently empty.

Use module-level imports:

- `from envoy_pyauth.middleware import AuthorizationMiddleware`
- `from envoy_pyauth.decorator import envoy_permission, envoy_internal_only`
- `from envoy_pyauth.utils import EnvoyQueryFilter`

Note:

- This repository also contains a top-level `__init__.py` (outside the package directory)
  with re-exports, but consumer code should prefer package-module imports above.

## Failure-mode behavior summary

- Middleware auth call failures: logged warning, `request.envoy` becomes `None`.
- Decorator context/shape errors: logged warning, HTTP 400 response.
- Query filter missing organization key (`KeyError`): returns `.none()`.
