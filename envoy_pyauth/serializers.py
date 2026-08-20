"""Serializer-level org scoping for write payloads.

``EnvoyQueryFilter`` scopes what a caller can *read*, and :class:`EnvoyObjectOrgOwnership`
scopes which row a write may *touch*. Neither covers the third case: a write whose payload
*references* another organization's row (``POST {"asset": <other org's id>}``). DRF's
``PrimaryKeyRelatedField`` resolves against the full table, so the reference is accepted and
the foreign row is silently pulled into the caller's org.

This module generalizes the two hand-rolled versions of that check that grew in-tree
(asset-service's ``ScopedRelatedFieldsMixin`` and user-management's ``validate_groups_scope`` /
``validate_designation_scope``) so services can drop their copies at their next pin bump.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings

from .utils import EnvoyQueryFilter

#: Shown when a related id is invisible to the caller's organization. Deliberately identical to
#: the "does not exist" case so a cross-tenant probe cannot distinguish "not yours" from
#: "not there".
SCOPED_FK_ERROR = "Object does not exist or you do not have permission to access it."


def session_customer_filter() -> bool:
    """The service's ``SESSION_CUSTOMER_FILTER`` setting, defaulting to enabled.

    Defaulting to ``True`` matters: a service that forgets the setting gets scoping rather
    than a silent fleet-wide bypass (F8).
    """
    return bool(getattr(settings, "SESSION_CUSTOMER_FILTER", True))


class ScopedRelatedFieldsMixin:
    """Narrow related-field querysets to the caller's Envoy scope.

    ``scoped_related_fields`` maps a serializer field name to the traversal that reaches
    ``organization_id`` from that field's model — e.g. ``asset`` scopes on ``organization_id``
    while ``meter`` scopes on ``asset__organization_id``.

    The scoped queryset follows the caller's isolation flag: while the org still reads the
    shared catalog, org-0 template rows remain referenceable; once the org is isolated, they
    are not — which is exactly the guarantee Phase 3's repoint depends on, since a payload that
    can still name an org-0 primitive can re-introduce the references the repoint just removed.
    """

    scoped_related_fields: dict[str, str] = {}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        request = self.context.get("request")  # type: ignore[attr-defined]
        for field_name, org_path in self.scoped_related_fields.items():
            field = self.fields.get(field_name)  # type: ignore[attr-defined]
            queryset = getattr(field, "queryset", None)
            if field is None or queryset is None:
                continue
            field.queryset = EnvoyQueryFilter.filter_queryset(
                request, queryset, session_customer_filter(), field_name=org_path
            )
            field.error_messages["does_not_exist"] = SCOPED_FK_ERROR


def scoped_object_or_error(request: Any, model: Any, pk: Any, *, field_name: str = "organization_id") -> Any:
    """Resolve ``pk`` within the caller's Envoy scope or raise ``ValidationError``.

    For raw ``*_id`` integer fields on action bodies, which bypass ``PrimaryKeyRelatedField``
    resolution entirely.
    """
    from rest_framework.serializers import ValidationError

    if pk is None:
        return None
    queryset = EnvoyQueryFilter.get_queryset(request, model, session_customer_filter(), field_name=field_name)
    obj = queryset.filter(pk=pk).first()
    if obj is None:
        raise ValidationError(SCOPED_FK_ERROR)
    return obj
