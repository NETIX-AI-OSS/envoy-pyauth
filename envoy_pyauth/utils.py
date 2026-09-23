from typing import Any, cast

from django.db.models import Q, QuerySet

from .types import EnvoyHttpRequest

#: Organization id of the platform template catalog. Platform callers act as this organization
#: to edit the shared templates; tenant callers read it only while their organization is not
#: isolated (see :func:`organization_is_isolated`).
TEMPLATE_ORG_ID = 0

#: Key user-management's ``/auth/me/`` snapshot uses for ``Organization.primitive_isolation_enabled``.
ISOLATION_FLAG_KEY = "organization_isolated"


def organization_is_isolated(request: EnvoyHttpRequest | None) -> bool:
    """Whether a tenant caller reads only its own organization, per the per-org cutover flag.

    user-management rides ``Organization.primitive_isolation_enabled`` to every service as
    ``request.envoy["organization_isolated"]``. Only an explicit boolean ``False`` means "still
    sharing the org-0 catalog"; a missing key, ``None``, ``True`` or any non-boolean value (a
    stale or hand-built payload carrying the string ``"false"``) is isolated. The flag can only
    ever widen a queryset when user-management says so in so many words.

    Flipping the flag off (``set_primitive_isolation --org N --off``, which also bumps that org's
    ``auth_version``) restores the ``[0, org]`` union for that organization without a library
    release: that is the per-org rollback lever.
    """
    envoy = getattr(request, "envoy", None) if request is not None else None
    if not isinstance(envoy, dict):
        return True
    return envoy.get(ISOLATION_FLAG_KEY) is not False


def scoped_org_ids(request: EnvoyHttpRequest | None, include_shared: bool | None = None) -> list[int]:
    """The organization ids a tenant caller may read: ``[org]``, or ``[0, org]`` while sharing.

    ``include_shared=None`` (the default) follows the caller's isolation flag — the union is
    included only when :func:`organization_is_isolated` is ``False``. ``include_shared=True``
    forces the union for the few platform-facing endpoints that genuinely aggregate across the
    template org; ``include_shared=False`` forces own-org-only regardless of the flag.
    """
    envoy = cast(dict[str, Any], getattr(request, "envoy", None) or {})
    org_id = envoy["organization"]
    if include_shared is None:
        include_shared = not organization_is_isolated(request)
    return [TEMPLATE_ORG_ID, org_id] if include_shared else [org_id]


class EnvoyQueryFilter:
    """Scope querysets to the caller's organization.

    A tenant caller sees its own organization, plus organization 0 (the shared template
    catalog) only while user-management reports its organization as not yet isolated — see
    :func:`organization_is_isolated` and :func:`scoped_org_ids`. The ``include_shared`` keyword
    overrides the flag per call.

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
