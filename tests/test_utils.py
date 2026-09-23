"""Unit tests for EnvoyQueryFilter's org scoping — pure branching tests, no Django DB."""

import pytest

from envoy_pyauth.utils import (
    EnvoyQueryFilter,
    organization_is_isolated,
    scoped_org_ids,
)


class FakeQuerySet:
    def __init__(self):
        self.calls = []

    def filter(self, *args, **kwargs):
        lookups = dict(kwargs)
        for q in args:
            lookups.update(dict(q.children))
        self.calls.append(("filter", lookups))
        return self

    def order_by(self, *fields):
        self.calls.append(("order_by", fields))
        return self

    def all(self):
        self.calls.append(("all", {}))
        return self

    def none(self):
        self.calls.append(("none", {}))
        return self


class FakeModel:
    def __init__(self):
        self.objects = FakeQuerySet()


class Req:
    def __init__(self, envoy):
        self.envoy = envoy


def get(request, session_customer_filter=True, **kwargs):
    model = FakeModel()
    return EnvoyQueryFilter.get_queryset(request, model, session_customer_filter, **kwargs).calls


def filtered(request, session_customer_filter=True, **kwargs):
    qs = FakeQuerySet()
    return EnvoyQueryFilter.filter_queryset(request, qs, session_customer_filter, **kwargs).calls


def test_tenant_caller_scopes_to_its_own_org_only():
    # No isolation flag in the snapshot is treated as isolated: the union needs an explicit False.
    assert get(Req({"organization": 7})) == [
        ("filter", {"organization_id__in": [7], "is_deleted": False}),
        ("order_by", ("id",)),
    ]


def test_tenant_caller_without_delete_filter_stays_scoped():
    assert get(Req({"organization": 7}), delete_filter=False) == [("filter", {"organization_id__in": [7]})]


def test_tenant_caller_honours_custom_field_name():
    assert get(Req({"organization": 7}), field_name="org", delete_filter=False) == [
        ("filter", {"org__in": [7]}),
    ]


def test_platform_caller_is_unscoped():
    # Q1 is unchanged by the retirement: acting as org 0 stays the sanctioned way to edit the
    # template catalog, so those callers keep the global view.
    assert get(Req({"organization": 0})) == [("filter", {"is_deleted": False}), ("order_by", ("id",))]
    assert get(Req({"organization": 0}), delete_filter=False) == [("all", {})]


def test_session_customer_filter_disabled_is_unscoped():
    assert get(Req({"organization": 7}), session_customer_filter=False) == [
        ("filter", {"is_deleted": False}),
        ("order_by", ("id",)),
    ]


def test_missing_envoy_fails_closed():
    assert get(Req(None)) == [("none", {})]
    assert get(Req({})) == [("none", {})]
    assert get(None) == [("none", {})]
    assert get(None, delete_filter=False) == [("none", {})]
    assert get(None, session_customer_filter=False) == [("none", {})]


def test_envoy_without_organization_returns_none():
    assert get(Req({"permissions": []})) == [("none", {})]


SCOPED_7 = [("filter", {"organization_id__in": [7], "is_deleted": False}), ("order_by", ("id",))]
SHARED_7 = [("filter", {"organization_id__in": [0, 7], "is_deleted": False}), ("order_by", ("id",))]


def test_tenant_with_isolation_flag_false_reads_the_shared_catalog():
    # primitive_isolation_enabled off in user-management: the org still reads org 0's templates.
    request = Req({"organization": 7, "organization_isolated": False})
    assert get(request) == SHARED_7
    assert filtered(request) == SHARED_7
    assert get(request, delete_filter=False) == [("filter", {"organization_id__in": [0, 7]})]
    assert filtered(request, delete_filter=False) == [("filter", {"organization_id__in": [0, 7]})]


def test_tenant_with_isolation_flag_true_reads_only_its_own_org():
    request = Req({"organization": 7, "organization_isolated": True})
    assert get(request) == SCOPED_7
    assert filtered(request) == SCOPED_7


def test_tenant_without_isolation_flag_reads_only_its_own_org():
    # A snapshot from before the flag existed (or any service stub) must not widen the queryset.
    request = Req({"organization": 7})
    assert get(request) == SCOPED_7
    assert filtered(request) == SCOPED_7


@pytest.mark.parametrize("flag", [None, "false", "False", 0, "", [], "0"])
def test_only_an_explicit_boolean_false_widens(flag):
    # A stringly or falsy-but-not-False value is ambiguous; ambiguity resolves to isolated.
    request = Req({"organization": 7, "organization_isolated": flag})
    assert get(request) == SCOPED_7
    assert filtered(request) == SCOPED_7


def test_include_shared_true_forces_the_union_even_for_an_isolated_org():
    for payload in (
        {"organization": 7},
        {"organization": 7, "organization_isolated": True},
        {"organization": 7, "organization_isolated": False},
    ):
        assert get(Req(payload), include_shared=True) == SHARED_7
        assert filtered(Req(payload), include_shared=True) == SHARED_7
        assert get(Req(payload), include_shared=True, delete_filter=False) == [
            ("filter", {"organization_id__in": [0, 7]})
        ]


def test_include_shared_false_forces_own_org_even_while_sharing():
    request = Req({"organization": 7, "organization_isolated": False})
    assert get(request, include_shared=False) == SCOPED_7
    assert filtered(request, include_shared=False) == SCOPED_7


@pytest.mark.parametrize("flag", [False, True, None])
@pytest.mark.parametrize("organization", [0, "0"])
def test_platform_caller_is_unscoped_whatever_the_flag(organization, flag):
    # Org-0 callers keep the global view; the flag and include_shared never narrow them.
    payload = {"organization": organization, "organization_isolated": flag}
    unscoped = [("filter", {"is_deleted": False}), ("order_by", ("id",))]
    assert get(Req(payload)) == unscoped
    assert filtered(Req(payload)) == unscoped
    assert get(Req(payload), include_shared=False) == unscoped
    assert get(Req(payload), delete_filter=False) == [("all", {})]


def test_superuser_tenant_caller_follows_the_same_flag_rule():
    # Only organization 0 is unscoped; a superuser acting inside a tenant org is scoped like any tenant.
    assert get(Req({"organization": 7, "is_superuser": True})) == SCOPED_7
    assert get(Req({"organization": 7, "is_superuser": True, "organization_isolated": False})) == SHARED_7


def test_session_customer_filter_disabled_ignores_the_flag():
    request = Req({"organization": 7, "organization_isolated": False})
    assert get(request, session_customer_filter=False) == [("filter", {"is_deleted": False}), ("order_by", ("id",))]


def test_missing_identity_fails_closed_whatever_the_flag():
    assert get(Req({"organization_isolated": False})) == [("none", {})]
    assert filtered(Req({"organization_isolated": False}), include_shared=True) == [("none", {})]


def test_organization_is_isolated():
    assert organization_is_isolated(Req({"organization": 7, "organization_isolated": False})) is False
    assert organization_is_isolated(Req({"organization": 7, "organization_isolated": True})) is True
    assert organization_is_isolated(Req({"organization": 7})) is True
    assert organization_is_isolated(Req({"organization": 7, "organization_isolated": "false"})) is True
    # No identity at all is the most isolated answer, never the widest.
    assert organization_is_isolated(Req(None)) is True
    assert organization_is_isolated(None) is True


def test_scoped_org_ids_helper():
    assert scoped_org_ids(Req({"organization": 7})) == [7]
    assert scoped_org_ids(Req({"organization": 7, "organization_isolated": True})) == [7]
    assert scoped_org_ids(Req({"organization": 7, "organization_isolated": False})) == [0, 7]
    assert scoped_org_ids(Req({"organization": 7}), include_shared=True) == [0, 7]
    assert scoped_org_ids(Req({"organization": 7, "organization_isolated": False}), include_shared=False) == [7]


def test_filter_queryset_mirrors_get_queryset():
    assert filtered(Req({"organization": 7})) == [
        ("filter", {"organization_id__in": [7], "is_deleted": False}),
        ("order_by", ("id",)),
    ]
    assert filtered(Req({"organization": 7}), delete_filter=False) == [("filter", {"organization_id__in": [7]})]
    assert filtered(Req({"organization": 0})) == [("filter", {"is_deleted": False}), ("order_by", ("id",))]
    assert filtered(Req({"organization": 0}), delete_filter=False) == [("all", {})]
    assert filtered(Req({"organization": 7}), session_customer_filter=False) == [
        ("filter", {"is_deleted": False}),
        ("order_by", ("id",)),
    ]
    assert filtered(Req(None)) == [("none", {})]
    assert filtered(Req({"permissions": []})) == [("none", {})]


def test_string_platform_organization_is_unscoped():
    assert get(Req({"organization": "0"})) == [("filter", {"is_deleted": False}), ("order_by", ("id",))]


def test_bogus_organization_fails_closed():
    assert get(Req({"organization": "bogus"})) == [("none", {})]
