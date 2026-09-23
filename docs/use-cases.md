# Use Cases

This document describes common ways to apply `envoy-pyauth` in Django/DRF services.

## 1) Gateway-authenticated Django service

A typical pattern is:

1. Client request arrives with `Authorization` header.
2. `AuthorizationMiddleware` forwards the token to an external auth endpoint.
3. Parsed user payload is attached to `request.envoy`.
4. View, decorators, and query utilities consume that payload.

This keeps auth lookup logic out of individual views.

## 2) Permission-gated API endpoints

Use `@envoy_permission("permission-name")` on DRF view methods where callers must hold a specific permission string.

Example use cases:

- Feature access by permission key.
- Role capability checks exposed through permission names.
- Service-level gates for privileged operations.

## 3) Internal-only endpoints

Use `@envoy_internal_only()` for routes that should not be accessible in normal external-auth user flow and are reserved for internal callers or control-plane style endpoints.

The caller must present a credential which `/auth/me/` resolves as platform-internal.
For a named service identity, opt it in explicitly:

```python
@envoy_internal_only(allowed_services=("tag-service",))
def post(self, request):
    ...
```

## 4) Organization-scoped data access

`EnvoyQueryFilter` scopes every tenant caller's queryset to the organization in
`request.envoy["organization"]`.

This can be used for list APIs, report endpoints, and model-backed services where a tenant boundary is required.

### The shared template catalog and the per-org isolation flag

Organization `0` is the shared platform template catalog. The org-0 primitive cloning
migration gives each organization its own copy of those primitives and repoints its rows onto
them; whether a tenant still reads organization `0` alongside its own is decided **per
organization** by user-management's `Organization.primitive_isolation_enabled`, which
`/auth/me/` emits as `organization_isolated` and the middleware attaches to `request.envoy`:

| `request.envoy["organization_isolated"]` | Tenant reads |
| --- | --- |
| `False` (boolean) | `[0, org]` — still sharing the template catalog |
| `True` | `[org]` — isolated onto its own clones |
| absent / `None` / anything else | `[org]` — the safe default |

`include_shared=True` on `get_queryset`/`filter_queryset` forces `[0, org]` for the few
platform-facing endpoints that genuinely aggregate across the template org;
`include_shared=False` forces `[org]`.

Restoring the union only widens **reads**. Writes to org-0 rows are still refused for tenant
callers by `EnvoyObjectOrgOwnership`, which checks the object's own `organization_id` and
never consults the union.

### Cutover and rollback

Both directions are a data change in user-management, not a library release:

```bash
# cutover (only after that org's repoint verification gate reports zero org-0 references)
python manage.py set_primitive_isolation --org 9 --on
# rollback: restores the [0, org] union for org 9 only
python manage.py set_primitive_isolation --org 9 --off
python manage.py set_primitive_isolation --all --status
```

Flipping `primitive_isolation_enabled` off and bumping that organization's users'
`auth_version` (the command does both) restores the union for that organization. The bump
drops user-management's cached `/auth/me/` payloads; each service's own identity cache holds a
payload for at most 30 seconds, so the change is fleet-wide within that window. No service
needs a redeploy or a different library pin.

Platform callers (`organization == 0`) are unchanged: they keep the unscoped global view, which
is what makes acting as org 0 the way to edit the template catalog.

## 5) Integration during local development

Attach a representative `request.envoy` identity in tests. Debug mode intentionally does
not alter authorization behavior.

See [API Reference](reference.md) and [Patterns](patterns.md) for exact behavior details.
