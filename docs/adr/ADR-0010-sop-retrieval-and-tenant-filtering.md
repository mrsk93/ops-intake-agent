# ADR-0010: Versioned Tenant-Scoped SOP Retrieval

- Status: Accepted for M6
- Date: 2026-09-06

## Decision

Store SOP documents and bounded chunks with tenant IDs, status, effective dates,
content hashes and explicit metadata columns for customer, location, service and
rule type. Retrieval SQL must filter tenant, approved status, effective window
and metadata before scoring. A retrieval run stores only a query hash, safe
filter snapshot, algorithm/version metadata and cited hit records; it does not
store the raw retrieval query in the run record.

For the synthetic MVP corpus, use a deterministic hybrid scorer: token overlap
plus a local hash-based 16-dimensional embedding, with deterministic tie
breaking. This keeps CI provider-free and makes retrieval reproducible. The
embedding is stored as a versioned JSON value rather than adding a pgvector
index before corpus size and query-plan evidence justify one. The provider port
can be added later without changing the tenant/effective-date contract.

Missing authoritative rules produce `RULE_NOT_FOUND`; the system never invents
a rule or falls back to another tenant. Citations include document/version
identity, bounded excerpt and chunk hash for operator review.

## Consequences

- Tenant isolation is enforced in the database query, not by post-filtering.
- Retired and future rules cannot influence a result at the repository seam.
- The local scorer is intentionally a deterministic baseline, not a claim of
  semantic quality or calibrated retrieval confidence.
- A later pgvector migration must preserve the same pre-ranking tenant and
  effective/status predicates and rerun the synthetic retrieval gold set.
