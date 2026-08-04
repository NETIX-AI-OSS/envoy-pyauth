"""Unit tests for EnvoyQueryFilter's org scoping — pure branching tests, no Django DB."""

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


def test_tenant_caller_scopes_to_org_zero_union():
    assert get(Req({"organization": 7})) == [
        ("filter", {"organization_id__in": [0, 7], "is_deleted": False}),
        ("order_by", ("id",)),
    ]


def test_tenant_caller_without_delete_filter_keeps_union_only():
    assert get(Req({"organization": 7}), delete_filter=False) == [("filter", {"organization_id__in": [0, 7]})]


def test_tenant_caller_honours_custom_field_name():
    assert get(Req({"organization": 7}), field_name="org", delete_filter=False) == [
        ("filter", {"org__in": [0, 7]}),
    ]


def test_platform_caller_is_unscoped():
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


def test_isolated_org_drops_the_shared_catalog():
    assert get(Req({"organization": 7, "organization_isolated": True})) == [
        ("filter", {"organization_id__in": [7], "is_deleted": False}),
        ("order_by", ("id",)),
    ]
    assert filtered(Req({"organization": 7, "organization_isolated": True}), delete_filter=False) == [
        ("filter", {"organization_id__in": [7]}),
    ]


def test_isolation_flag_tolerates_stringly_values():
    # The DEBUG payload and historical cached payloads carry "true"/"false" strings, and
    # bool("false") is True — which would isolate every org the moment the field appears.
    assert get(Req({"organization": 7, "organization_isolated": "true"})) == [
        ("filter", {"organization_id__in": [7], "is_deleted": False}),
        ("order_by", ("id",)),
    ]
    assert get(Req({"organization": 7, "organization_isolated": "false"})) == [
        ("filter", {"organization_id__in": [0, 7], "is_deleted": False}),
        ("order_by", ("id",)),
    ]


def test_missing_isolation_flag_keeps_shared_catalog():
    # Payloads predating the field (and 300s-cached ones mid-deploy) must not isolate.
    assert organization_is_isolated(Req({"organization": 7})) is False
    assert get(Req({"organization": 7})) == [
        ("filter", {"organization_id__in": [0, 7], "is_deleted": False}),
        ("order_by", ("id",)),
    ]


def test_include_shared_overrides_the_flag_in_both_directions():
    isolated = Req({"organization": 7, "organization_isolated": True})
    shared = Req({"organization": 7})
    assert get(isolated, include_shared=True, delete_filter=False) == [("filter", {"organization_id__in": [0, 7]})]
    assert get(shared, include_shared=False, delete_filter=False) == [("filter", {"organization_id__in": [7]})]


def test_scoped_org_ids_helper():
    assert scoped_org_ids(Req({"organization": 7})) == [0, 7]
    assert scoped_org_ids(Req({"organization": 7, "organization_isolated": True})) == [7]
    assert scoped_org_ids(Req({"organization": 7}), include_shared=False) == [7]


def test_isolated_platform_caller_stays_unscoped():
    # Q1: org-0 callers keep the global view regardless of any flag on the payload.
    assert get(Req({"organization": 0, "organization_isolated": True})) == [
        ("filter", {"is_deleted": False}),
        ("order_by", ("id",)),
    ]


def test_filter_queryset_mirrors_get_queryset():
    assert filtered(Req({"organization": 7})) == [
        ("filter", {"organization_id__in": [0, 7], "is_deleted": False}),
        ("order_by", ("id",)),
    ]
    assert filtered(Req({"organization": 7}), delete_filter=False) == [("filter", {"organization_id__in": [0, 7]})]
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
