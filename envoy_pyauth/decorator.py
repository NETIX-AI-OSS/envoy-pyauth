import functools
import logging
from collections.abc import Callable
from typing import Any, TypeVar, cast

from rest_framework import status
from rest_framework.response import Response

from .common import DJANGO_DEBUG

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def envoy_auth_exempt(view: F) -> F:
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

    setattr(view, "_envoy_auth_exempt", True)

    if isinstance(view, type):
        return view

    @functools.wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        return view(*args, **kwargs)

    setattr(wrapped, "_envoy_auth_exempt", True)
    return cast(F, wrapped)


def envoy_permission(permission_name: str) -> Callable[[F], F]:
    def decorator(function: F) -> F:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if DJANGO_DEBUG:
                return function(*args, **kwargs)
            request = args[1]
            try:
                if permission_name not in request.envoy["permissions"]:
                    return Response(status=status.HTTP_403_FORBIDDEN)
            except Exception as e:
                logger.warning(str(e))
                return Response(status=status.HTTP_400_BAD_REQUEST)
            return function(*args, **kwargs)

        return cast(F, wrapper)

    return decorator


def envoy_internal_only() -> Callable[[F], F]:
    def decorator(function: F) -> F:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if DJANGO_DEBUG:
                return function(*args, **kwargs)
            request = args[1]
            try:
                if getattr(request, "envoy", False):
                    return Response(status=status.HTTP_403_FORBIDDEN)
            except Exception as e:
                logger.warning(str(e))
                return Response(status=status.HTTP_400_BAD_REQUEST)
            return function(*args, **kwargs)

        return cast(F, wrapper)

    return decorator
