from typing import Any

from django.db.models import Q, QuerySet

from .types import EnvoyHttpRequest


class EnvoyQueryFilter:
    @staticmethod
    def _identity(request: EnvoyHttpRequest | None) -> dict[str, Any] | None:
        envoy = getattr(request, "envoy", None) if request is not None else None
        if not isinstance(envoy, dict):
            return None
        organization = envoy.get("organization")
        if organization in (None, "", "bogus"):
            return None
        return envoy

    @staticmethod
    def _unscoped(queryset: QuerySet[Any], delete_filter: bool) -> QuerySet[Any]:
        if delete_filter:
            return queryset.filter(is_deleted=False).order_by("id")
        return queryset.all()

    @classmethod
    def get_queryset(
        cls,
        request: EnvoyHttpRequest | None,
        model: Any,
        session_customer_filter: bool,
        field_name: str = "organization_id",
        delete_filter: bool = True,
    ) -> QuerySet[Any]:
        envoy = cls._identity(request)
        if envoy is None:
            return model.objects.none()
        if not session_customer_filter or str(envoy["organization"]) == "0":
            return cls._unscoped(model.objects, delete_filter)
        org_id = envoy["organization"]
        if delete_filter:
            return model.objects.filter(
                Q(
                    **{
                        f"{field_name}__in": [0, org_id],
                        "is_deleted": False,
                    }
                )
            ).order_by("id")
        return model.objects.filter(
            Q(
                **{
                    f"{field_name}__in": [0, org_id],
                }
            )
        )

    @classmethod
    def filter_queryset(
        cls,
        request: EnvoyHttpRequest | None,
        queryset: QuerySet[Any],
        session_customer_filter: bool,
        field_name: str = "organization_id",
        delete_filter: bool = True,
    ) -> QuerySet[Any]:
        envoy = cls._identity(request)
        if envoy is None:
            return queryset.none()
        if not session_customer_filter or str(envoy["organization"]) == "0":
            return cls._unscoped(queryset, delete_filter)
        org_id = envoy["organization"]
        if delete_filter:
            return queryset.filter(
                Q(
                    **{f"{field_name}__in": [0, org_id]},
                    is_deleted=False,
                )
            ).order_by("id")
        return queryset.filter(
            Q(
                **{f"{field_name}__in": [0, org_id]},
            )
        )
