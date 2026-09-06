# Domain Context

## Intake terminology

- **SOP document**: a tenant-owned versioned source of operational rules. Only an
  approved document whose effective window contains the retrieval time is
  authoritative for validation.
- **SOP chunk**: a bounded, hash-addressed excerpt of one SOP document with
  source coordinates and optional customer/location/service metadata.
- **Retrieval run**: an immutable record of one tenant-scoped rule lookup,
  identified by a query hash, filter snapshot and algorithm version.
- **Rule citation**: the operator-facing reference to an effective SOP chunk;
  it includes document/version identity, a bounded excerpt and content hash.
- **Intake graph thread**: the stable workflow cursor for one intake run. Its
  checkpoint contains references and decisions, not raw document content.
- **Review interrupt**: a persisted pause that requires an authorized human
  response before a workflow can continue.
