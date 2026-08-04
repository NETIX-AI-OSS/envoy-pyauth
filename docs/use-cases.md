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

Before v3.0.0 this also unioned in the global organization (`0`), the shared template catalog
every tenant read from. The org-0 primitive cloning migration gave each organization its own
copy of those primitives and repointed their rows onto it, so the union has been removed;
`include_shared=True` re-admits it for the few platform-facing endpoints that genuinely
aggregate across the template org.

Platform callers (`organization == 0`) are unchanged: they keep the unscoped global view, which
is what makes acting as org 0 the way to edit the template catalog.

## 5) Integration during local development

Attach a representative `request.envoy` identity in tests. Debug mode intentionally does
not alter authorization behavior.

See [API Reference](reference.md) and [Patterns](patterns.md) for exact behavior details.
