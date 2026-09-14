# Changelog

> Reconstructed from git history on 2026-09-14. The entries below were derived after the
> fact from the commits and diffs between release tags, not written at release time. They
> are accurate about what changed, but they are not a substitute for release notes and may
> omit user-visible detail nobody recorded. Entries from the next release onward are written
> as part of the release.

Releases before `v2.0.0` are not covered here: this file was written to close the gap that
was blocking consumers held at `v2.0.0` from scoping a move to `v3.0.0`.

## Unreleased — 4.0.0

`pyproject.toml` already declares `4.0.0`, but **no `v4.0.0` tag exists**. This is unreleased
work on `main`; do not treat the declared version as a published release.

### Changed — BREAKING

- **Safe methods are now gated by default.** `resolve_required_permission` previously returned
  `None` for any `SAFE_METHODS` request, so reads on a viewset declaring `permission_module`
  were open to every authenticated caller. It now returns `f"{module}-view"`. A viewset that
  intentionally exposes authenticated reads must set `allow_ungated_safe_methods = True`.
  Before pinning a service to this version, grant the existing `<module>-view` codenames to
  the intended roles and mark deliberately ungated reads with the opt-out — otherwise reads
  that worked before will return 403.

### Changed

- CI: migrated `ubuntu-latest` jobs to the `build-only` runner.

## 3.0.0 — 2026-08-20 (tag `v3.0.0`)

### Changed — BREAKING: tenant scoping no longer unions organization 0

This is the "pre-v3 scoping semantics" change that consumers held at `v2.0.0` need in order
to scope their upgrade, so it is described in full.

Through `v2.0.0`, `EnvoyQueryFilter` scoped a tenant caller's queryset with
`organization_id__in=[0, org_id]` — every tenant read implicitly included organization 0,
the shared platform template catalog that all tenants drew their primitives from. As of
`v3.0.0` a tenant caller sees only its own organization: the filter is built from
`scoped_org_ids(request)`, which returns `[org_id]`. The union is gone because the org-0
primitive cloning migration is complete — each organization now owns cloned copies of the
template primitives, so re-admitting org 0 would only re-expose the template rows the
migration moved every tenant off. Platform callers (`organization == 0`) are unchanged and
keep the unscoped global view, which remains the sanctioned way to edit the template catalog.

**What this means for a consumer.** If a service's data was fully cloned by the migration,
the change is invisible: the rows the caller used to reach through org 0 are now its own.
If a service still has rows that only exist under organization 0 — a repoint that never
finished, a fixture loaded only into the template org — those rows disappear from tenant
querysets on upgrade, and the symptom is an empty list rather than an error. That is the
risk to scope before bumping a pin: for each model filtered by `EnvoyQueryFilter`, confirm
no tenant-visible rows remain owned by organization 0.

**Escape hatch.** `EnvoyQueryFilter.get_queryset` / `filter_queryset` take a new
`include_shared` keyword. `include_shared=True` restores `[0, org_id]` for the handful of
platform-facing endpoints that genuinely aggregate across the template org. It is never
derived from the request: widening a queryset automatically is exactly how an unfinished
repoint goes unnoticed, so the caller has to ask for it explicitly.

### Added

- `envoy_pyauth.utils.scoped_org_ids(request, include_shared=None)` — the organization ids a
  caller may read.
- `envoy_pyauth.utils.TEMPLATE_ORG_ID` — named constant for the template catalog org id,
  replacing the literal `0` in the filter.
- `envoy_pyauth.cloning` — the org-prefixed machine key (`nc<org_id>_`) and clone-provenance
  conventions, previously re-derived independently in each service that clones the catalog.
- `envoy_pyauth.serializers` — serializer-level org scoping for write payloads, so a write
  that *references* another organization's row by primary key is rejected rather than
  silently pulling the foreign row into the caller's org. Generalizes two hand-rolled
  in-service versions of the same check.

### Deprecated

- `envoy_pyauth.utils.organization_is_isolated(request)` is retained for compatibility but
  no longer varies: it returns `True` for any resolved tenant caller. Code branching on it
  can be deleted.

### Changed

- Docs (`docs/reference.md`, `docs/use-cases.md`) updated for the new scoping semantics.
- Collapsed multi-line comments and docstrings to single-line across the package. This
  removed a large amount of explanatory prose from `permissions.py`, `middleware.py` and
  `decorator.py`; no behaviour changed with it.
- Cleaned up docs, license headers and docstrings.

### Note on `2.1.0`

The release commit is titled "per-org isolation flag (v2.1.0) and retire the `[0, org]` union
(v3.0.0)": both steps landed in a single commit and only `v3.0.0` was ever tagged. There is
no `v2.1.0` release.

## 2.0.0 — 2026-08-18 (tag `v2.0.0`)

Baseline for this file; its own changes are not reconstructed here. The fail-closed
authentication and authorization guarantees in effect at this version are documented in the
repository README under "Behavior Notes".
