from typing import Any, cast

from django.db.models import Q, QuerySet

from .types import EnvoyHttpRequest

#: Organization id of the platform template catalog. Platform callers act as this organization
#: to edit the shared templates; tenant callers no longer read it (see the module note below).
TEMPLATE_ORG_ID = 0


def organization_is_isolated(request: EnvoyHttpRequest | None) -> bool:
    """Retained for compatibility; every tenant organization is isolated as of v3.0.0.

    The org-0 primitive cloning migration is complete: each organization owns its primitives,
    so ``organization_isolated`` no longer varies. Callers still reading this flag get ``True``
    for any resolved tenant caller, and code branching on it can be deleted.
    """
    envoy = getattr(request, "envoy", None) if request is not None else None
    return bool(envoy)


def scoped_org_ids(request: EnvoyHttpRequest | None, include_shared: bool | None = None) -> list[int]:
    """The organization ids a tenant caller may read — its own, and only its own.

    ``include_shared=True`` is the one remaining way to re-admit the org-0 catalog, and it
    exists for the handful of platform-facing endpoints that genuinely aggregate across the
    template org. It is never derived from the request any more: an organization that still
    needed the union would be one whose repoint never finished, and silently widening its
    queryset is how that goes unnoticed.
    """
    envoy = cast(dict[str, Any], getattr(request, "envoy", None) or {})
    org_id = envoy["organization"]
    return [TEMPLATE_ORG_ID, org_id] if include_shared else [org_id]


class EnvoyQueryFilter:
    """Scope querysets to the caller's organization.

    As of v3.0.0 a tenant caller sees only its own rows. Before the org-0 primitive cloning
    migration this unioned in organization 0, the shared template catalog every tenant read
    from; now each organization owns cloned copies of those primitives, so the union would only
    re-expose the template rows the migration moved everyone off.

    Platform callers (``organization == 0``) are unchanged: they keep the unscoped global view,
    which is what makes acting as org 0 the sanctioned way to edit the template catalog.
    """

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
        include_shared: bool | None = None,
    ) -> QuerySet[Any]:
        envoy = cls._identity(request)
        if envoy is None:
            return model.objects.none()
        if not session_customer_filter or str(envoy["organization"]) == str(TEMPLATE_ORG_ID):
            return cls._unscoped(model.objects, delete_filter)
        org_ids = scoped_org_ids(request, include_shared)
        if delete_filter:
            return model.objects.filter(
                Q(
                    **{
                        f"{field_name}__in": org_ids,
                        "is_deleted": False,
                    }
                )
            ).order_by("id")
        return model.objects.filter(
            Q(
                **{
                    f"{field_name}__in": org_ids,
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
        include_shared: bool | None = None,
    ) -> QuerySet[Any]:
        envoy = cls._identity(request)
        if envoy is None:
            return queryset.none()
        if not session_customer_filter or str(envoy["organization"]) == str(TEMPLATE_ORG_ID):
            return cls._unscoped(queryset, delete_filter)
        org_ids = scoped_org_ids(request, include_shared)
        if delete_filter:
            return queryset.filter(
                Q(
                    **{f"{field_name}__in": org_ids},
                    is_deleted=False,
                )
            ).order_by("id")
        return queryset.filter(
            Q(
                **{f"{field_name}__in": org_ids},
            )
        )
