# Patterns

## Middleware enrichment pattern

`AuthorizationMiddleware` enriches each request with normalized auth context in `request.envoy`.

Benefits:

- Centralized auth-context retrieval logic.
- Uniform data contract for downstream code.
- Reduced duplication across views.

## Decorator-based authorization pattern

`envoy_permission(permission_name)` wraps view functions and enforces a required permission string from `request.envoy["permissions"]`.

Behavior:

- Permitted: execute wrapped function.
- Not permitted: return HTTP 403.
- Missing/malformed context: return HTTP 400.

## Internal-only gate pattern

`envoy_internal_only()` is a specialized gate for internal route usage semantics.

Behavior (current implementation):

- In non-debug mode, requests with truthy `request.envoy` return HTTP 403.
- Requests without truthy `request.envoy` continue to wrapped function.

This behavior is intentionally documented as-is and should be considered when designing endpoint exposure.

## Multi-tenant queryset scoping pattern

`EnvoyQueryFilter` uses `organization_id` scoping with support for global rows.

Pattern details:

- For scoped requests, query includes `organization_id in [0, request.envoy["organization"]]`.
- Optional soft-delete filtering controlled by `delete_filter`.
- Supports model-level entry (`get_queryset`) and queryset-level entry (`filter_queryset`).

## Debug-first integration pattern

The library includes debug-oriented branches controlled by `DJANGO_DEBUG == "TRUE"`.

Intent:

- Support rapid local integration.
- Allow endpoint/dev flow testing when external auth dependencies are not fully wired.

Production and deployment teams should document how `DJANGO_DEBUG` is managed per environment.
