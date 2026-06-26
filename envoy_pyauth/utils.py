from typing import Any, cast

from django.db.models import Q, QuerySet

from .types import EnvoyHttpRequest


class EnvoyQueryFilter:
    @classmethod
    def get_queryset(
        cls,
        request: EnvoyHttpRequest | None,
        model: Any,
        session_customer_filter: bool,
        field_name: str = "organization_id",
        delete_filter: bool = True,
    ) -> QuerySet[Any]:
        try:
            if (
                request is None
                or not session_customer_filter
                or not getattr(request, "envoy", False)
                or cast(dict[str, Any], request.envoy)["organization"] == 0
            ):
                if delete_filter:
                    return model.objects.filter(
                        is_deleted=False,
                    ).order_by("id")
                return model.objects.all()
        except KeyError:
            return model.objects.none()
        envoy = cast(dict[str, Any], request.envoy)
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
        try:
            if (
                request is None
                or not session_customer_filter
                or not getattr(request, "envoy", False)
                or cast(dict[str, Any], request.envoy)["organization"] == 0
            ):
                if delete_filter:
                    return queryset.filter(
                        is_deleted=False,
                    ).order_by("id")
                return queryset.all()
        except KeyError:
            return queryset.none()
        envoy = cast(dict[str, Any], request.envoy)
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
