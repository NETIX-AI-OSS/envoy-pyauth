from django.db.models import Q


class EnvoyQueryFilter:
    @classmethod
    def get_queryset(
        cls,
        request,
        model,
        session_customer_filter,
        field_name="organization_id",
        delete_filter=True,
    ):
        try:
            if (
                request is None
                or not session_customer_filter
                or not getattr(request, "envoy", False)
                or request.envoy["organization"] == 0
            ):
                if delete_filter:
                    return model.objects.filter(
                        is_deleted=False,
                    ).order_by("id")
                else:
                    return model.objects.all()
        except KeyError:
            return model.objects.none()
        if delete_filter:
            return model.objects.filter(
                Q(
                    **{
                        f"{field_name}__in": [0, request.envoy["organization"]],
                        "is_deleted": False,
                    }
                )
            ).order_by("id")
        else:
            return model.objects.filter(
                Q(
                    **{
                        f"{field_name}__in": [0, request.envoy["organization"]],
                    }
                )
            )

    @classmethod
    def filter_queryset(
        cls,
        request,
        queryset,
        session_customer_filter,
        field_name="organization_id",
        delete_filter=True,
    ):
        try:
            if (
                request is None
                or not session_customer_filter
                or not getattr(request, "envoy", False)
                or request.envoy["organization"] == 0
            ):
                if delete_filter:
                    return queryset.filter(
                        is_deleted=False,
                    ).order_by("id")
                else:
                    return queryset.all()
        except KeyError:
            return queryset.none()
        if delete_filter:
            return queryset.filter(
                Q(
                    **{f"{field_name}__in": [0, request.envoy["organization"]]},
                    is_deleted=False,
                )
            ).order_by("id")
        else:
            return queryset.filter(
                Q(
                    **{f"{field_name}__in": [0, request.envoy["organization"]]},
                )
            )
