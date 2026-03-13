# envoy-pyauth Documentation

`envoy-pyauth` is a Django-focused integration library that centralizes Envoy-authenticated identity and authorization context into request handling.

## Who should use this library

Use this library if you:

- Run Django or DRF services behind an Envoy/API-gateway style auth boundary.
- Need request-time identity context (`request.envoy`) shared consistently across views.
- Want lightweight permission decorators and organization-scoped query filtering in application code.

## What this library provides

- Middleware to fetch user context from an external auth service and attach it to `request.envoy`.
- Decorators for permission checks and internal-only route handling.
- Query filter helpers for organization-scoped and soft-delete-aware queryset behavior.

## Documentation map

- [Use Cases](use-cases.md)
- [Architecture](architecture.md)
- [Patterns](patterns.md)
- [API Reference](reference.md)

## Quick start links

For installation and a compact setup example, see the project [README](../README.md).
