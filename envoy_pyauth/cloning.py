"""Conventions shared by every service that clones the org-0 template catalog.

The org-0 primitive cloning migration gives each organization its own copy of the platform
catalog. Two conventions have to hold identically in seven services, so they live here rather
than being re-derived per repo:

**Org-prefixed machine keys.** A clone keeps its template's ``display_name`` byte-identical —
that is the verified cross-service name contract (viz class bindings, tag EQUIP_INHERIT rules
and denormalized ``PointTagDict.equipType`` values all match on display names) — and prefixes
the machine-facing identifier with ``nc<org_id>_``. The key space is then isolated per
organization, so uniqueness holds by construction whether the underlying constraint happens to
be per-org or global.

**Provenance.** A clone records where it came from, at which template revision, and whether
the tenant has since edited it. That is what makes later template evolution possible:
additions propagate, modifications only touch un-customized clones, deletions never propagate.
"""

from __future__ import annotations

import re

#: Organization id of the platform template catalog.
TEMPLATE_ORG_ID = 0

ORG_KEY_PREFIX = "nc"
_ORG_KEY_RE = re.compile(rf"^{ORG_KEY_PREFIX}(?P<org>\d+)_(?P<base>.*)$", re.DOTALL)

#: Column names every cloneable model gains. Plain columns, not foreign keys: the sources are
#: multi-table-inherited in asset-service and a cascade from a template onto live tenant rows
#: is exactly what must not happen.
PROVENANCE_FIELDS = ("cloned_from_id", "template_revision", "is_customized")


def org_prefix(org_id: int) -> str:
    """The key prefix owned by ``org_id`` — ``nc3_`` for organization 3."""
    return f"{ORG_KEY_PREFIX}{int(org_id)}_"


def org_key(name: str, org_id: int) -> str:
    """Return ``name`` as ``org_id``'s machine key.

    Idempotent, and re-homing is explicit: a key already prefixed for *another* organization is
    re-prefixed from its base rather than nested, so ``nc3_fire_alarm`` cloned into org 5 is
    ``nc5_fire_alarm`` and never ``nc5_nc3_fire_alarm``. Applies only to identifier columns
    (``name``, ``key``, ``code``, ``slug``, ``path``) — never to display columns.
    """
    return f"{org_prefix(org_id)}{base_key(name)}"


def base_key(name: str) -> str:
    """The template-relative key: ``nc3_fire_alarm`` -> ``fire_alarm``, others unchanged."""
    match = _ORG_KEY_RE.match(name or "")
    return match.group("base") if match else (name or "")


def key_owner(name: str) -> int | None:
    """The organization a prefixed key belongs to, or ``None`` when it carries no prefix."""
    match = _ORG_KEY_RE.match(name or "")
    return int(match.group("org")) if match else None


def is_org_key(name: str, org_id: int) -> bool:
    """Whether ``name`` is already ``org_id``'s key."""
    return key_owner(name) == int(org_id)
