# ADR-0007: Artifact Quarantine and Deterministic Parsing

- Status: Accepted
- Date: 2026-09-06

## Decision

- Uploads are streamed through bounded chunks, hashed with SHA-256, and written to a tenant-scoped quarantine key before safety inspection. A valid artifact is copied to an accepted key; rejected content is deleted from storage while its safe rejection code remains in the database.
- File acceptance requires both a plausible extension and byte signature. Encrypted documents, macro-like Office containers, mismatched MIME declarations and configured size/page/table limits fail closed. Filenames are sanitized before display or storage metadata use.
- `StoragePort` remains the application seam. Local filesystem storage is for development, S3-compatible storage is the Compose/production path, and deterministic fakes are used in CI. No public object URL is returned.
- Parsers are deterministic and preserve evidence coordinates. CSV and XLSX use local parsers, email is reduced to text, digital PDF text is extracted locally, and image/scanned PDF paths call only the `OcrProvider` port. Parser output includes parser/provider versions, hashes, warnings and artifact/page/sheet/cell coordinates.
- Duplicate identity is `(tenant_id, content_sha256, artifact_role)`. A different hash with the same tenant-local external request reference is marked as a possible amendment through `review_required` and an immutable predecessor link.

## Consequences

- CI and local tests require no API key, OCR account or operations credential.
- Quarantine storage can contain transient untrusted bytes, so cleanup and retention are explicit operations and all reads remain tenant-scoped.
- Parsed output is currently returned as a versioned evidence map; canonical extraction and durable derived-artifact persistence are deferred to M4.
