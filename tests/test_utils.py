"""Unit tests for EnvoyQueryFilter's org scoping — pure branching tests, no Django DB."""

from envoy_pyauth.utils import EnvoyQueryFilter, scoped_org_ids


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
    # v2: the org-0 union is gone. Every organization owns cloned primitives, so unioning the
    # template catalog back in would only re-expose the rows the migration moved everyone off.
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


def test_isolation_flag_no_longer_widens_the_queryset():
    # The flag is dead weight now: an organization whose repoint never finished would be one
    # that still needs the union, and silently widening its queryset is how that goes unnoticed.
    for payload in ({"organization": 7}, {"organization": 7, "organization_isolated": "false"}):
        assert get(Req(payload)) == [
            ("filter", {"organization_id__in": [7], "is_deleted": False}),
            ("order_by", ("id",)),
        ]


def test_include_shared_is_the_only_way_back_to_the_union():
    # Retained for the few platform-facing endpoints that genuinely aggregate across the
    # template org; never derived from the request.
    assert get(Req({"organization": 7}), include_shared=True, delete_filter=False) == [
        ("filter", {"organization_id__in": [0, 7]})
    ]


def test_scoped_org_ids_helper():
    assert scoped_org_ids(Req({"organization": 7})) == [7]
    assert scoped_org_ids(Req({"organization": 7}), include_shared=True) == [0, 7]


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
