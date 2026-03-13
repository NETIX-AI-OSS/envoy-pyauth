import os
import logging
import requests
from django.utils.deprecation import MiddlewareMixin
from .common import DJANGO_DEBUG

logger = logging.getLogger(__name__)


class AuthorizationMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, *view_args, **view_kwargs):
        if DJANGO_DEBUG:
            request.envoy = {
                "username": "DEBUG",
                "is_superuser": "true",
                "user_type": "organization",
                "organization": 0,
                "site_id": None,
                "permissions": ["sample-permission"],
                "groups": ["groups"],
                "feature_flags": "feature_1",
            }
        try:
            token = request.META.get("HTTP_AUTHORIZATION")
            if token is None:
                token = os.getenv("USER_SVC_AUTH")
            payload = None
            api_url = os.getenv("USER_AUTH_SVC_URL", "http://user-management-auth.backend:8001") + "/auth/me/"
            try:
                api_response = requests.get(api_url, headers={"Authorization": f"{token}"})
                api_response.raise_for_status()
                payload = api_response.json()
                logger.debug(f"API response: {payload}")
            except requests.RequestException as api_error:
                logger.warning("Error while calling external API: %s", str(api_error))
            request.envoy = payload
        except Exception as e:
            logger.warning(str(e))
        return None
