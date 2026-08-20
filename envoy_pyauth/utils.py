from typing import Any, cast

from django.db.models import Q, QuerySet

from .types import EnvoyHttpRequest

#: Organization id of the platform template catalog. Tenant callers read these rows through the
#: ``[0, org]`` union until their organization is migrated onto its own cloned primitives.
TEMPLATE_ORG_ID = 0


def _envoy_flag(envoy: dict[str, Any], key: str) -> bool:
    """Read a boolean flag off the envoy payload, tolerating stringly values.

    ``/auth/me/`` emits native booleans, but the DEBUG payload and historical cached payloads
    carry ``"true"`` / ``"false"`` strings — and ``bool("false")`` is ``True``, which would
    silently invert every flag it touches.
    """
    return str(envoy.get(key)).lower() == "true"


def organization_is_isolated(request: EnvoyHttpRequest | None) -> bool:
    """Whether the caller's organization owns its primitives and must not read org 0.

    Driven by ``Organization.primitive_isolation_enabled`` in user-management, which rides the
    ``/auth/me/`` snapshot as ``organization_isolated``. Defaults to ``False``: an organization
    that has not been migrated (or a payload predating the field) keeps today's shared-catalog
    behaviour, so the flag is safe to deploy ahead of any migration.
    """
    envoy = getattr(request, "envoy", None) if request is not None else None
    if not envoy:
        return False
    return _envoy_flag(cast(dict[str, Any], envoy), "organization_isolated")


def scoped_org_ids(request: EnvoyHttpRequest | None, include_shared: bool | None = None) -> list[int]:
    """The organization ids a tenant caller may read.

    ``[org]`` once the caller's organization is isolated, ``[0, org]`` while it still reads the
    shared template catalog. ``include_shared`` overrides the flag in both directions for call
    sites that know better (e.g. a service whose primitives are already fully per-org).
    """
    envoy = cast(dict[str, Any], getattr(request, "envoy", None) or {})
    org_id = envoy["organization"]
    if include_shared is None:
        include_shared = not organization_is_isolated(request)
    return [TEMPLATE_ORG_ID, org_id] if include_shared else [org_id]


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
