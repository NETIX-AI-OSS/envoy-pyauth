"""Unit tests for EnvoyQueryFilter's org scoping.

Pure branching tests — no Django DB. ``FakeQuerySet`` records the ORM calls the filter makes
so each branch can be asserted on lookups instead of rows.
"""

from envoy_pyauth.utils import EnvoyQueryFilter


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


def test_missing_envoy_is_unscoped():
    assert get(Req(None)) == [("filter", {"is_deleted": False}), ("order_by", ("id",))]
    assert get(Req({})) == [("filter", {"is_deleted": False}), ("order_by", ("id",))]
    assert get(None) == [("filter", {"is_deleted": False}), ("order_by", ("id",))]
    assert get(None, delete_filter=False) == [("all", {})]


def test_envoy_without_organization_returns_none():
    assert get(Req({"permissions": []})) == [("none", {})]


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
    assert filtered(Req(None)) == [("filter", {"is_deleted": False}), ("order_by", ("id",))]
    assert filtered(Req({"permissions": []})) == [("none", {})]
