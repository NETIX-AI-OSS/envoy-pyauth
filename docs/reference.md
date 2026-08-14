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

There is no environment-variable fallback for inbound identity.

Auth URL behavior:

- Base from `USER_AUTH_SVC_URL`.
- Default base: `http://user-management-auth.backend:8001`.
- Effective endpoint: `<base>/auth/me/`.

Assignment behavior:

- On success with a valid identity envelope: `request.envoy = api_response.json()`.
- On request errors: warning log, then `request.envoy = None`.
- On outer exception: warning log and returns `None`.

Positive cache behavior:

- Cache keys contain only a SHA-256 digest of the credential.
- `ENVOY_AUTH_CACHE_TTL` may lower the lifetime but cannot exceed 30 seconds.
- A JWT `exp` claim shortens the cache lifetime further.
- Payloads without `organization` plus a list-like `permissions` value are rejected.

`DJANGO_DEBUG` never injects identity and never changes this behavior.

## Module: `envoy_pyauth.decorator`

### `envoy_permission(permission_name)`

Returns a decorator that wraps a view function.

Behavior:

- Supports function views, bound methods, and a `request=` keyword argument.
- Missing/malformed identity returns DRF `Response(status=401)`.
- A resolved caller without the codename returns `Response(status=403)`.
- A caller holding the codename executes the wrapped function.

### `envoy_internal_only(*, allowed_services=())`

Returns a decorator that wraps a view function.

Behavior:

- Missing identity returns 401.
- Platform-internal identity executes the wrapped function.
- A named service identity executes only if its `service_name` is explicitly included
  in `allowed_services`.
- All other identities return 403.
- The legacy user-management platform-internal envelope (`user_id=0`, organization 0,
  superuser, username `platform_internal`) is accepted for rollout compatibility.

## Module: `envoy_pyauth.utils`

### `class EnvoyQueryFilter`

#### `get_queryset(request, model, session_customer_filter, field_name="organization_id", delete_filter=True)`

Returns a model queryset filtered according to request/envoy context.

Fail-closed branch returns `model.objects.none()` when identity is missing, malformed,
or carries an unresolved organization.

The broad/default query is returned only for an authenticated identity when either:

- `session_customer_filter` is false, or
- the resolved organization is numeric or string `0`.

Fallback results:

- If `delete_filter=True`: `model.objects.filter(is_deleted=False).order_by("id")`
- Else: `model.objects.all()`

Scoped branch:

- Filters on `field_name__in=[0, request.envoy["organization"]]`
- Applies `is_deleted=False` when `delete_filter=True`
- Orders by `id` in delete-filter branch

Invalid identity behavior: returns `model.objects.none()`.

#### `filter_queryset(request, queryset, session_customer_filter, field_name="organization_id", delete_filter=True)`

Same branching behavior as `get_queryset`, but operates on an existing queryset instance.

## Module: `envoy_pyauth.common`

### `DJANGO_DEBUG`

Compatibility export parsed with a safe false default. It is not consulted by any
authentication or authorization decision.

## Import surface

The package module `envoy_pyauth/__init__.py` initializes Django typing support.

Use module-level imports:

- `from envoy_pyauth.middleware import AuthorizationMiddleware`
- `from envoy_pyauth.decorator import envoy_permission, envoy_internal_only`
- `from envoy_pyauth.utils import EnvoyQueryFilter`

Note:

- This repository also contains a top-level `__init__.py` (outside the package directory)
  with re-exports, but consumer code should prefer package-module imports above.

## Failure-mode behavior summary

- Middleware auth call failures: logged warning, `request.envoy` becomes `None`.
- Missing/malformed decorator identity: HTTP 401 response.
- Authenticated permission/service mismatch: HTTP 403 response.
- Query filter missing organization key (`KeyError`): returns `.none()`.
