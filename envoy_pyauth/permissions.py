"""Reusable DRF permission classes for Envoy-authenticated services.

The Envoy middleware only *annotates* ``request.envoy`` (it never rejects), and the
``EnvoyQueryFilter`` scoping fails *open* when ``request.envoy`` is absent. So a service
that sets no ``DEFAULT_PERMISSION_CLASSES`` is effectively ``AllowAny`` on every write.
These classes make enforcement fail *closed*:

* :class:`HasEnvoy` — require a resolved Envoy identity. Use as the platform-wide
  ``DEFAULT_PERMISSION_CLASSES`` so unauthenticated / failed-auth requests are rejected
  (401/403) instead of falling through.

* :class:`EnvoyActionPermissions` — per-action permission gate for viewsets. Resolves the
  codename required for the current action (via the view's ``get_required_permission()`` or
  its ``required_permissions`` map) and checks it against the caller's canonical permission
  list (``request.envoy["permissions"]`` — bare codenames, as emitted by ``/auth/me/``).

* :func:`require_permissions` — factory building a permission class that requires one or
  more codenames, for ``APIView`` / ``@action`` endpoints outside the CRUD map.

All classes honour ``DJANGO_DEBUG`` the same way the decorators do (full bypass in local
debug), so behaviour is consistent across the codebase.
"""

from __future__ import annotations

from collections.abc import Iterable

from rest_framework.permissions import SAFE_METHODS, BasePermission

from .common import DJANGO_DEBUG


def _envoy_permissions(request) -> frozenset[str]:
    """The caller's canonical permission codenames (empty when unauthenticated)."""
    envoy = getattr(request, "envoy", None)
    if not envoy:
        return frozenset()
    return frozenset(envoy.get("permissions", ()))


# Write actions map to a verb; reads (SAFE_METHODS) are never gated by default so a fresh
# "<module>-view" codename nobody holds yet cannot black out reads. Custom write actions
# default to "edit".
_WRITE_VERB_BY_ACTION = {
    "create": "edit",
    "update": "edit",
    "partial_update": "edit",
    "destroy": "delete",
}


def resolve_required_permission(view) -> str | None:
    """Canonical per-action codename resolver for BaseViewSet-style viewsets.

    This is the single source of truth every service's ``BaseViewSet.get_required_permission``
    should delegate to (previously each repo copy-pasted an identical body, which had begun to
    diverge). Resolution order:

    1. an explicit ``view.required_permissions[view.action]`` mapping wins (per-action override,
       and the only way to gate a specific *read*);
    2. otherwise, with no ``view.permission_module`` the action is ungated (``None``);
    3. reads (SAFE_METHODS) stay open (``None``);
    4. writes derive ``f"{permission_module}-{verb}"`` (``edit`` for create/update, ``delete`` for
       destroy, ``edit`` for any custom write action).
    """
    action = getattr(view, "action", None)
    req_map = getattr(view, "required_permissions", None) or {}
    if action in req_map:
        return req_map[action]
    module = getattr(view, "permission_module", None)
    if not module:
        return None
    method = getattr(getattr(view, "request", None), "method", "GET")
    if method in SAFE_METHODS:
        return None
    verb = _WRITE_VERB_BY_ACTION.get(action, "edit")
    return f"{module}-{verb}"


class HasEnvoy(BasePermission):
    """Fail-closed authentication: require a resolved Envoy identity.

    Intended as the platform-wide ``DEFAULT_PERMISSION_CLASSES`` entry. Because the
    middleware sets ``request.envoy = None`` on any auth failure, this rejects
    unauthenticated and failed-auth requests that would otherwise pass through.
    """

    message = "Authentication required."

    def has_permission(self, request, view) -> bool:
        if DJANGO_DEBUG:
            return True
        return bool(getattr(request, "envoy", None))


class EnvoyActionPermissions(HasEnvoy):
    """Per-action codename gate for viewsets.

    Requires a resolved Envoy identity (via :class:`HasEnvoy`) and, when the view maps the
    current action to a permission codename, that the caller holds it. The required codename
    is resolved from, in order:

    1. ``view.get_required_permission()`` if the view defines it (returns a codename or
       ``None``); this is what ``BaseViewSet`` implements from ``permission_module`` +
       ``required_permissions``.
    2. otherwise ``view.required_permissions[view.action]``.

    A resolved value of ``None`` means "no explicit gate": the action is allowed for any
    authenticated caller (reads stay open to tenant members; a service opts individual
    writes into enforcement by mapping them).
    """

    message = "You do not have permission to perform this action."

    def has_permission(self, request, view) -> bool:
        if DJANGO_DEBUG:
            return True
        if not super().has_permission(request, view):
            return False
        codename = self._required_permission(view)
        if codename is None:
            return True
        return codename in _envoy_permissions(request)

    @staticmethod
    def _required_permission(view) -> str | None:
        # A view may override get_required_permission() for bespoke logic; otherwise the
        # canonical resolver derives the codename from permission_module / required_permissions
        # so a viewset needs no per-repo boilerplate (see resolve_required_permission).
        getter = getattr(view, "get_required_permission", None)
        if callable(getter):
            return getter()
        return resolve_required_permission(view)


def require_permissions(*codenames: str, require_all: bool = True) -> type[BasePermission]:
    """Build a permission class requiring the given codename(s).

    Use on ``APIView`` / ``@action`` endpoints that sit outside a viewset CRUD map::

        permission_classes = [require_permissions("gateway-config-apply")]

    ``require_all=False`` requires *any* of the codenames instead of all.
    """

    required: tuple[str, ...] = tuple(codenames)

    class _RequirePermissions(HasEnvoy):
        message = "You do not have permission to perform this action."

        def has_permission(self, request, view) -> bool:
            if DJANGO_DEBUG:
                return True
            if not super().has_permission(request, view):
                return False
            held = _envoy_permissions(request)
            check = all if require_all else any
            return check(code in held for code in required)

    _RequirePermissions.__name__ = "RequirePermissions_" + "_".join(c.replace("-", "_") for c in required)
    return _RequirePermissions


def has_permissions(request, codenames: Iterable[str], require_all: bool = True) -> bool:
    """Imperative check for use inside view bodies (e.g. object-level branching)."""
    if DJANGO_DEBUG:
        return True
    held = _envoy_permissions(request)
    check = all if require_all else any
    return check(code in held for code in codenames)
