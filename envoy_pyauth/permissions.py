"""Reusable DRF permission classes and query helpers that make Envoy-authenticated enforcement fail closed."""

from __future__ import annotations

from collections.abc import Iterable

from rest_framework.permissions import SAFE_METHODS, BasePermission


def _envoy_permissions(request) -> frozenset[str]:
    """The caller's canonical permission codenames (empty when unauthenticated)."""
    envoy = getattr(request, "envoy", None)
    if not envoy:
        return frozenset()
    permissions = envoy.get("permissions", ())
    if isinstance(permissions, str) or not isinstance(permissions, Iterable):
        return frozenset()
    return frozenset(str(permission) for permission in permissions)


def _has_envoy_identity(request) -> bool:
    """Return whether the request carries the minimum trusted identity envelope."""
    envoy = getattr(request, "envoy", None)
    return (
        isinstance(envoy, dict)
        and envoy.get("organization") not in (None, "", "bogus")
        and isinstance(envoy.get("permissions"), (list, tuple, set, frozenset))
    )


_WRITE_VERB_BY_ACTION = {
    "create": "edit",
    "update": "edit",
    "partial_update": "edit",
    "destroy": "delete",
}


def resolve_required_permission(view) -> str | None:
    """Resolve an action codename, requiring ``<module>-view`` for safe methods by default.

    A view that intentionally exposes authenticated reads may set
    ``allow_ungated_safe_methods = True``. Keeping that exception explicit makes
    new ``permission_module`` declarations fail closed without preventing a
    reviewed public-within-the-tenant endpoint from opting out.
    """
    action = getattr(view, "action", None)
    req_map = getattr(view, "required_permissions", None) or {}
    if action is not None and action in req_map:
        return req_map[action]
    module = getattr(view, "permission_module", None)
    if not module:
        return None
    method = getattr(getattr(view, "request", None), "method", "GET")
    if method in SAFE_METHODS:
        if getattr(view, "allow_ungated_safe_methods", False) is True:
            return None
        return f"{module}-view"
    verb = _WRITE_VERB_BY_ACTION.get(action if isinstance(action, str) else "", "edit")
    return f"{module}-{verb}"


class HasEnvoy(BasePermission):
    """Fail-closed authentication: require a resolved Envoy identity (intended as the platform-wide default permission class)."""

    message = "Authentication required."

    def has_permission(self, request, view) -> bool:
        return _has_envoy_identity(request)


class EnvoyActionPermissions(HasEnvoy):
    """Per-action codename gate: requires a resolved Envoy identity and, when the view maps the current action to a permission, that the caller holds it."""

    message = "You do not have permission to perform this action."

    def has_permission(self, request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        codename = self._required_permission(view)
        if codename is None:
            return True
        return codename in _envoy_permissions(request)

    @staticmethod
    def _required_permission(view) -> str | None:
        # get_required_permission() overrides the canonical resolver fallback.
        getter = getattr(view, "get_required_permission", None)
        if callable(getter):
            return getter()
        return resolve_required_permission(view)


class EnvoyObjectOrgOwnership(BasePermission):
    """Object-level ownership gate: writes require the caller's organization to own the object; reads and platform callers are exempt."""

    message = "This record belongs to another organization."

    def has_object_permission(self, request, view, obj) -> bool:
        envoy = getattr(request, "envoy", None)
        if not isinstance(envoy, dict) or not _has_envoy_identity(request):
            return False
        if request.method in SAFE_METHODS:
            return True
        caller = envoy.get("organization")
        # organization may be a string, or "bogus" if it could not be resolved.
        if str(caller) == "0" or str(envoy.get("is_superuser")).lower() == "true":
            return True
        owner = getattr(obj, "organization_id", None)
        return owner is not None and str(owner) == str(caller)


def require_permissions(*codenames: str, require_all: bool = True) -> type[BasePermission]:
    """Build a permission class requiring the given codename(s) (``require_all=False`` for any-of instead of all-of)."""

    required: tuple[str, ...] = tuple(codenames)

    class _RequirePermissions(HasEnvoy):
        message = "You do not have permission to perform this action."

        def has_permission(self, request, view) -> bool:
            if not super().has_permission(request, view):
                return False
            held = _envoy_permissions(request)
            check = all if require_all else any
            return check(code in held for code in required)

    _RequirePermissions.__name__ = "RequirePermissions_" + "_".join(c.replace("-", "_") for c in required)
    return _RequirePermissions


def has_permissions(request, codenames: Iterable[str], require_all: bool = True) -> bool:
    """Imperative check for use inside view bodies (e.g. object-level branching)."""
    if not _has_envoy_identity(request):
        return False
    held = _envoy_permissions(request)
    check = all if require_all else any
    return check(code in held for code in codenames)
