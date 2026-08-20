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

#### `get_queryset(request, model, session_customer_filter, field_name="organization_id", delete_filter=True, include_shared=None)`

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

- Filters on `field_name__in=scoped_org_ids(request, include_shared)` — `[org]`. The `[0, org]`
  union was removed in v3.0.0: every organization now owns cloned primitives, so unioning the
  template catalog back in would only re-expose the rows the migration moved everyone off
- Applies `is_deleted=False` when `delete_filter=True`
- Orders by `id` in delete-filter branch

Invalid identity behavior: returns `model.objects.none()`.

#### `filter_queryset(request, queryset, session_customer_filter, field_name="organization_id", delete_filter=True, include_shared=None)`

Same branching behavior as `get_queryset`, but operates on an existing queryset instance.

### `organization_is_isolated(request)`

**Deprecated in v3.0.0** — returns `True` for any resolved tenant caller. Every organization
owns its primitives now, so the flag no longer varies and code branching on it can be deleted.

### `scoped_org_ids(request, include_shared=None)`

The organization ids a tenant caller may read: `[org]`, or `[0, org]` when `include_shared=True`
is passed explicitly. It is never derived from the request — an organization that still needed
the union would be one whose repoint never finished, and silently widening its queryset is how
that goes unnoticed.

### `TEMPLATE_ORG_ID`

`0` — the platform template catalog organization.

## Module: `envoy_pyauth.serializers`

### `class ScopedRelatedFieldsMixin`

Narrows related-field querysets to the caller's Envoy scope via a
`scoped_related_fields = {field_name: org_traversal}` map, so a write payload cannot reference
another organization's row. Follows the caller's isolation flag, so an isolated org can no
longer name org-0 primitives in a payload.

### `scoped_object_or_error(request, model, pk, *, field_name="organization_id")`

Scope-resolves a raw `*_id` value from an action body, raising `ValidationError` when it is
not visible to the caller.

### `SCOPED_FK_ERROR`

The shared message for both "not yours" and "not there", so cross-tenant probes cannot tell
the two apart.

## Module: `envoy_pyauth.cloning`

Conventions shared by every service that clones the org-0 template catalog.

### `org_key(name, org_id)` / `org_prefix(org_id)`

Machine-key prefixing: `org_key("fire_alarm_systems", 3)` is `"nc3_fire_alarm_systems"`.
Idempotent, and re-homing replaces rather than nests (`nc3_x` cloned into org 5 is `nc5_x`).
Applies to identifier columns (`name`, `key`, `code`, `slug`, `path`) only — display columns
are copied byte-identical, because display names are the cross-service name contract.

### `base_key(name)` / `key_owner(name)` / `is_org_key(name, org_id)`

Inverse helpers: the template-relative key, the owning organization (or `None`), and a
membership test.

### `PROVENANCE_FIELDS`

`("cloned_from_id", "template_revision", "is_customized")` — the columns every cloneable model
gains. Plain columns rather than foreign keys: the sources are multi-table-inherited in
asset-service, and a cascade from a template onto live tenant rows is precisely what must not
happen.

### `TEMPLATE_ORG_ID`

`0`.

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
