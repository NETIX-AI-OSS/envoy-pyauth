"""Unit tests for the reusable DRF permission classes.

Pure permission-logic tests — no Django DB. They rely on ``request.envoy`` being a plain
dict (as the middleware sets it) and a lightweight view stub mirroring ``BaseViewSet``.
"""

from types import SimpleNamespace

from rest_framework.permissions import SAFE_METHODS

from envoy_pyauth.permissions import (
    EnvoyActionPermissions,
    EnvoyObjectOrgOwnership,
    HasEnvoy,
    has_permissions,
    require_permissions,
    resolve_required_permission,
)


class Req:
    def __init__(self, perms=None, method="POST"):
        self.envoy = None if perms is None else {"permissions": list(perms)}
        self.method = method


class View:
    """Mirror of BaseViewSet.get_required_permission for test purposes.

    Reads (safe HTTP methods) stay open by default; only writes are gated.
    """

    _VERB = {
        "create": "edit",
        "update": "edit",
        "partial_update": "edit",
        "destroy": "delete",
    }

    def __init__(self, action=None, module=None, req_map=None, method="GET"):
        self.action = action
        self.permission_module = module
        self.required_permissions = req_map or {}
        self.request = SimpleNamespace(method=method)

    def get_required_permission(self):
        if self.action in self.required_permissions:
            return self.required_permissions[self.action]
        if not self.permission_module:
            return None
        if self.request.method in SAFE_METHODS:
            return None
        return f"{self.permission_module}-{self._VERB.get(self.action, 'edit')}"


def test_has_envoy_fails_closed_for_unauthenticated():
    assert HasEnvoy().has_permission(Req(perms=None), View()) is False
    assert HasEnvoy().has_permission(Req(perms=[]), View()) is True


def test_action_gate_reads_open_when_module_declared():
    # Reads stay open even when a module is declared, so a fresh <module>-view codename
    # that no role holds yet cannot black out reads.
    gate = EnvoyActionPermissions()
    assert gate.has_permission(Req([]), View(action="list", module="tag", method="GET")) is True
    assert gate.has_permission(Req([]), View(action="retrieve", module="tag", method="GET")) is True


def test_action_gate_explicit_read_map_still_enforced():
    gate = EnvoyActionPermissions()
    view = View(action="list", module="tag", req_map={"list": "tag-view"}, method="GET")
    assert gate.has_permission(Req([]), view) is False
    assert gate.has_permission(Req(["tag-view"]), view) is True


def test_action_gate_writes_require_edit_and_delete():
    gate = EnvoyActionPermissions()
    assert gate.has_permission(Req(["tag-view"]), View(action="create", module="tag", method="POST")) is False
    assert gate.has_permission(Req(["tag-edit"]), View(action="create", module="tag", method="POST")) is True
    assert gate.has_permission(Req(["tag-edit"]), View(action="destroy", module="tag", method="DELETE")) is False
    assert gate.has_permission(Req(["tag-delete"]), View(action="destroy", module="tag", method="DELETE")) is True


def test_action_gate_open_when_no_permission_mapped():
    gate = EnvoyActionPermissions()
    assert gate.has_permission(Req([]), View(action="list")) is True
    assert gate.has_permission(Req([]), View(action="frobnicate")) is True


def test_action_gate_custom_action_override_and_default():
    gate = EnvoyActionPermissions()
    v = View(action="apply", module="gateway", req_map={"apply": "gateway-config-apply"}, method="POST")
    assert gate.has_permission(Req(["gateway-edit"]), v) is False
    assert gate.has_permission(Req(["gateway-config-apply"]), v) is True
    # custom WRITE action with a module but no override defaults to <module>-edit
    assert gate.has_permission(Req([]), View(action="sync", module="tag", method="POST")) is False
    assert gate.has_permission(Req(["tag-edit"]), View(action="sync", module="tag", method="POST")) is True
    # custom READ action with a module stays open
    assert gate.has_permission(Req([]), View(action="preview", module="tag", method="GET")) is True


def test_require_permissions_factory():
    all_of = require_permissions("gateway-config-apply")()
    assert all_of.has_permission(Req(["gateway-config-apply"]), View()) is True
    assert all_of.has_permission(Req(["gateway-edit"]), View()) is False
    assert all_of.has_permission(Req(perms=None), View()) is False

    any_of = require_permissions("a", "b", require_all=False)()
    assert any_of.has_permission(Req(["b"]), View()) is True
    assert any_of.has_permission(Req(["c"]), View()) is False


def test_has_permissions_imperative():
    assert has_permissions(Req(["x"]), ["x"]) is True
    assert has_permissions(Req(["x"]), ["y"]) is False


class _ResolverView:
    """View stub with NO get_required_permission override — exercises the canonical resolver."""

    def __init__(self, action=None, module=None, req_map=None, method="GET"):
        self.action = action
        self.permission_module = module
        self.required_permissions = req_map or {}
        self.request = SimpleNamespace(method=method)


def test_resolve_required_permission_canonical():
    # No module -> ungated.
    assert resolve_required_permission(_ResolverView(action="list")) is None
    # Reads stay open even with a module declared.
    assert resolve_required_permission(_ResolverView(action="list", module="tag", method="GET")) is None
    assert resolve_required_permission(_ResolverView(action="retrieve", module="tag", method="GET")) is None
    # Writes derive edit/delete.
    assert resolve_required_permission(_ResolverView(action="create", module="tag", method="POST")) == "tag-edit"
    assert resolve_required_permission(_ResolverView(action="partial_update", module="tag", method="PATCH")) == "tag-edit"
    assert resolve_required_permission(_ResolverView(action="destroy", module="tag", method="DELETE")) == "tag-delete"
    # Custom write action defaults to edit; explicit override wins.
    assert resolve_required_permission(_ResolverView(action="sync", module="tag", method="POST")) == "tag-edit"
    view = _ResolverView(action="apply", module="gateway", req_map={"apply": "gateway-config-apply"}, method="POST")
    assert resolve_required_permission(view) == "gateway-config-apply"
    # Explicit read gate still enforced.
    read_gate = _ResolverView(action="list", module="tag", req_map={"list": "tag-view"}, method="GET")
    assert resolve_required_permission(read_gate) == "tag-view"


def test_action_gate_uses_canonical_resolver_without_view_method():
    # A view with NO get_required_permission still resolves via the permission class fallback.
    gate = EnvoyActionPermissions()
    assert gate.has_permission(Req(["tag-edit"]), _ResolverView(action="create", module="tag", method="POST")) is True
    assert gate.has_permission(Req([]), _ResolverView(action="create", module="tag", method="POST")) is False
    assert gate.has_permission(Req([]), _ResolverView(action="list", module="tag", method="GET")) is True


class OrgReq:
    """Request stub carrying only the envoy org identity."""

    def __init__(self, org=None, method="PATCH", is_superuser=False, envoy=True):
        self.envoy = {"organization": org, "is_superuser": is_superuser} if envoy else None
        self.method = method


def _obj(owner):
    return SimpleNamespace(organization_id=owner)


def test_object_ownership_reads_never_blocked():
    gate = EnvoyObjectOrgOwnership()
    for method in SAFE_METHODS:
        assert gate.has_object_permission(OrgReq(org=7, method=method), View(), _obj(0)) is True
        assert gate.has_object_permission(OrgReq(org=7, method=method), View(), _obj(9)) is True


def test_object_ownership_platform_callers_exempt():
    gate = EnvoyObjectOrgOwnership()
    assert gate.has_object_permission(OrgReq(org=0), View(), _obj(7)) is True
    assert gate.has_object_permission(OrgReq(org=7, is_superuser=True), View(), _obj(9)) is True
    assert gate.has_object_permission(OrgReq(org=7, is_superuser="true"), View(), _obj(9)) is True


def test_object_ownership_stringly_false_superuser_not_exempt():
    # The auth payload can carry is_superuser as the string "false"; truthiness must not exempt it.
    gate = EnvoyObjectOrgOwnership()
    assert gate.has_object_permission(OrgReq(org=7, is_superuser="false"), View(), _obj(0)) is False
    assert gate.has_object_permission(OrgReq(org=7, is_superuser="False"), View(), _obj(9)) is False


def test_object_ownership_no_envoy_falls_open():
    # Authentication is HasEnvoy's job; this gate only compares orgs.
    gate = EnvoyObjectOrgOwnership()
    assert gate.has_object_permission(OrgReq(envoy=False), View(), _obj(7)) is True


def test_object_ownership_unowned_object_allowed():
    gate = EnvoyObjectOrgOwnership()
    assert gate.has_object_permission(OrgReq(org=7), View(), _obj(None)) is True
    assert gate.has_object_permission(OrgReq(org=7), View(), SimpleNamespace()) is True


def test_object_ownership_tolerates_string_organizations():
    gate = EnvoyObjectOrgOwnership()
    assert gate.has_object_permission(OrgReq(org="7"), View(), _obj(7)) is True
    assert gate.has_object_permission(OrgReq(org="0"), View(), _obj(7)) is True
    assert gate.has_object_permission(OrgReq(org="7"), View(), _obj(9)) is False
    # "bogus" is the unresolved-organization sentinel — it owns nothing.
    assert gate.has_object_permission(OrgReq(org="bogus"), View(), _obj(7)) is False


def test_object_ownership_own_rows_writable():
    gate = EnvoyObjectOrgOwnership()
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        assert gate.has_object_permission(OrgReq(org=7, method=method), View(), _obj(7)) is True


def test_object_ownership_denies_org0_and_foreign_rows():
    gate = EnvoyObjectOrgOwnership()
    for method in ("PUT", "PATCH", "DELETE"):
        assert gate.has_object_permission(OrgReq(org=7, method=method), View(), _obj(0)) is False
        assert gate.has_object_permission(OrgReq(org=7, method=method), View(), _obj(9)) is False
    assert EnvoyObjectOrgOwnership.message == "This record belongs to another organization."
