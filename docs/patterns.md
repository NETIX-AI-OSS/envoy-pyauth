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
- Missing/malformed context: return HTTP 401.

## Internal-only gate pattern

`envoy_internal_only()` is a specialized gate for internal route usage semantics.

Behavior:

- A platform-internal identity is permitted. The current legacy user-management
  envelope is recognized while services migrate to `is_platform_internal=true`.
- Named `user_type=service` identities are permitted only when their `service_name`
  appears in the decorator's `allowed_services` argument.
- Missing identity returns HTTP 401; other identities return HTTP 403.

## Multi-tenant queryset scoping pattern

`EnvoyQueryFilter` uses `organization_id` scoping, admitting the global template rows
(organization `0`) only for organizations that have not been isolated onto their own clones.

Pattern details:

- For scoped requests, query is `organization_id in [request.envoy["organization"]]`, widened
  to `[0, organization]` only when `request.envoy["organization_isolated"] is False` (or the
  call passes `include_shared=True`). See [Use Cases](use-cases.md#4-organization-scoped-data-access).
- Optional soft-delete filtering controlled by `delete_filter`.
- Supports model-level entry (`get_queryset`) and queryset-level entry (`filter_queryset`).
- A missing, incomplete, or unresolved identity returns `.none()`, even when the
  tenant-filter flag is disabled.

## Local integration pattern

`DJANGO_DEBUG` does not bypass any security decision. Tests should attach an explicit
identity; genuinely public routes should use `@envoy_auth_exempt`.
