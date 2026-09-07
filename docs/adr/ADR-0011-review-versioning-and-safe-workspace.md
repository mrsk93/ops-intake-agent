# ADR-0011: Review Versioning and Evidence-First Workspace

- Status: Accepted
- Date: 2026-09-07

## Decision

Represent operator review as immutable `DraftVersion` and
`ValidationSnapshot` records selected by a tenant-scoped `Review` pointer.
Every editable field carries evidence references; an edit must cite evidence
already attached to that field, include a concise reason, and create a new
draft, validation snapshot and optimistic review version. Warning
acknowledgements and revalidation also advance the review version.

Action previews persist the canonical payload, validation snapshot, draft
version, review version, payload hash and stable idempotency key. Any later
edit or revalidation therefore makes the previous preview stale. Verified
actions lock the review from further edits, warning changes and revalidation.

The web workspace is a three-panel synthetic fixture: source text is rendered
as escaped data, fields show their evidence, and issues/rules remain separate
from action preview. It does not call a model or operations system directly.

## Consequences

- Stale concurrent edits and stale previews fail closed at the API boundary.
- The database is the source of truth for evidence, versions and validation;
  client state is only a presentation aid.
- The workspace can demonstrate missing and conflicting evidence without
  using customer documents or external provider credentials.
- A future live review client must preserve the same version/hash contracts.
