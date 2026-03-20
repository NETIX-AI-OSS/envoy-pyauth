import functools

from rest_framework import status
from rest_framework.response import Response
import logging

from .common import DJANGO_DEBUG

logger = logging.getLogger(__name__)


def envoy_auth_exempt(view):
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

    view._envoy_auth_exempt = True

    if isinstance(view, type):
        return view

    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        return view(*args, **kwargs)

    wrapped._envoy_auth_exempt = True
    return wrapped


def envoy_permission(permission_name):
    def decorator(function):
        def wrapper(*args, **kwargs):
            if DJANGO_DEBUG:
                result = function(*args, **kwargs)
                return result
            request = args[1]
            try:
                if not permission_name in request.envoy["permissions"]:
                    return Response(status=status.HTTP_403_FORBIDDEN)
            except Exception as e:
                logger.warning(str(e))
                return Response(status=status.HTTP_400_BAD_REQUEST)
            result = function(*args, **kwargs)
            return result

        return wrapper

    return decorator


def envoy_internal_only():
    def decorator(function):
        def wrapper(*args, **kwargs):
            if DJANGO_DEBUG:
                result = function(*args, **kwargs)
                return result
            request = args[1]
            try:
                if getattr(request, "envoy", False):
                    return Response(status=status.HTTP_403_FORBIDDEN)
            except Exception as e:
                logger.warning(str(e))
                return Response(status=status.HTTP_400_BAD_REQUEST)
            result = function(*args, **kwargs)
            return result

        return wrapper

    return decorator
