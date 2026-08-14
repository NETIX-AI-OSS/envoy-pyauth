import functools
from collections.abc import Callable
from typing import Any, TypeVar, cast

from rest_framework import status
from rest_framework.response import Response

F = TypeVar("F", bound=Callable[..., Any])


def _request_from_call(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    """Find the request for both function views and bound view methods."""
    request = kwargs.get("request")
    if request is not None:
        return request
    for candidate in args:
        if hasattr(candidate, "envoy") or hasattr(candidate, "META"):
            return candidate
    return None


def _permissions(identity: Any) -> frozenset[str] | None:
    if not isinstance(identity, dict):
        return None
    if identity.get("organization") in (None, "", "bogus"):
        return None
    values = identity.get("permissions")
    if not isinstance(values, (list, tuple, set, frozenset)):
        return None
    return frozenset(str(value) for value in values)


def _true(value: Any) -> bool:
    return value is True or (isinstance(value, str) and value.lower() == "true")


def _platform_internal(identity: Any) -> bool:
    """Recognize explicit and legacy platform-internal ``/auth/me/`` envelopes."""
    if not isinstance(identity, dict):
        return False
    if _true(identity.get("is_platform_internal")):
        return True
    # Compatibility with the current user-management PlatformInternalUser payload.
    return (
        identity.get("username") == "platform_internal"
        and str(identity.get("user_id")) == "0"
        and str(identity.get("organization")) == "0"
        and _true(identity.get("is_superuser"))
    )


def _named_service(identity: Any, allowed_services: frozenset[str]) -> bool:
    if not allowed_services or not isinstance(identity, dict):
        return False
    return identity.get("user_type") == "service" and identity.get("service_name") in allowed_services


def envoy_auth_exempt[T: Callable[..., Any]](view: T) -> T:
    """Mark a view or viewset action as exempt from Envoy auth middleware.

    Usage:
        @envoy_auth_exempt
        def my_public_view(request):
            ...

        @envoy_auth_exempt
        class MyPublicView(APIView):
            ...

        class MyViewSet(viewsets.ModelViewSet):
            @envoy_auth_exempt
            def list(self, request):
                ...
    """

    view._envoy_auth_exempt = True  # type: ignore[attr-defined]

    if isinstance(view, type):
        return view

    @functools.wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        return view(*args, **kwargs)

    wrapped._envoy_auth_exempt = True  # type: ignore[attr-defined]
    return cast(T, wrapped)


def envoy_permission(permission_name: str) -> Callable[[F], F]:
    def decorator(function: F) -> F:
        @functools.wraps(function)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            request = _request_from_call(args, kwargs)
            permissions = _permissions(getattr(request, "envoy", None))
            if permissions is None:
                return Response(status=status.HTTP_401_UNAUTHORIZED)
            if permission_name not in permissions:
                return Response(status=status.HTTP_403_FORBIDDEN)
            return function(*args, **kwargs)

        return cast(F, wrapper)

    return decorator


def envoy_internal_only(*, allowed_services: tuple[str, ...] = ()) -> Callable[[F], F]:
    """Require a platform-internal or explicitly allow-listed named service identity.

    ``allowed_services`` only applies to identities carrying both ``user_type=service``
    and a matching ``service_name``. An absent identity never represents an internal call.
    """

    service_names = frozenset(allowed_services)

    def decorator(function: F) -> F:
        @functools.wraps(function)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            request = _request_from_call(args, kwargs)
            identity = getattr(request, "envoy", None)
            if _permissions(identity) is None:
                return Response(status=status.HTTP_401_UNAUTHORIZED)
            if _platform_internal(identity) or _named_service(identity, service_names):
                return function(*args, **kwargs)
            return Response(status=status.HTTP_403_FORBIDDEN)

        return cast(F, wrapper)

    return decorator
