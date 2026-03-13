# Architecture

## Component model

`envoy-pyauth` has three main components:

- `AuthorizationMiddleware` (`envoy_pyauth.middleware`)
- Decorators (`envoy_pyauth.decorator`)
- Query filtering utilities (`envoy_pyauth.utils`)

The middleware is the integration boundary with your auth service. Decorators and query helpers consume the attached context.

## Request lifecycle

1. **Incoming request** enters Django middleware chain.
2. **Authorization token resolution**:
   - First from `request.META["HTTP_AUTHORIZATION"]`.
   - Fallback from `USER_SVC_AUTH` environment variable.
3. **Auth service call**:
   - URL: `USER_AUTH_SVC_URL` + `/auth/me/`
   - Default base URL: `http://user-management-auth.backend:8001`
4. **Payload assignment**:
   - Successful response JSON is assigned to `request.envoy`.
   - On request/HTTP errors, payload remains `None` and `request.envoy` is set accordingly.
5. **View execution phase**:
   - Decorators evaluate `request.envoy`.
   - Query helpers use `request.envoy["organization"]` for scoping.

## Context contract (`request.envoy`)

Expected keys (as used by library logic):

- `permissions` (iterable of permission strings)
- `organization` (organization identifier; `0` used as global/system value)

Additional keys (example from debug payload) may include:

- `username`, `is_superuser`, `user_type`, `site_id`, `groups`, `feature_flags`

## Environment variable contract

- `DJANGO_DEBUG` (required by current implementation)
  - Parsed as string equality check: `os.environ["DJANGO_DEBUG"] == "TRUE"`
- `USER_AUTH_SVC_URL` (optional)
  - Default: `http://user-management-auth.backend:8001`
- `USER_SVC_AUTH` (optional)
  - Used when request header token is not present.

## Dependency boundaries

- **Django**: middleware base class and queryset operations.
- **Django REST Framework**: decorator responses/status handling.
- **requests**: outbound auth service call.

The package intentionally stays lightweight and pushes identity source-of-truth to an external auth service.
