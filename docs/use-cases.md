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

## 4) Organization-scoped data access

`EnvoyQueryFilter` supports multi-tenant access behavior by filtering `organization_id` against:

- global records (`0`), and
- the organization in `request.envoy["organization"]`.

This can be used for list APIs, report endpoints, and model-backed services where a tenant boundary is required.

## 5) Debug integration during local development

When `DJANGO_DEBUG` is set to `TRUE`, middleware/decorators include debug-oriented behavior to reduce setup friction while developing and debugging integration paths.

See [API Reference](reference.md) and [Patterns](patterns.md) for exact behavior details.
