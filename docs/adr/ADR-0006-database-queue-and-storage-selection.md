# ADR-0006: Database, Queue and Storage Selection

- Status: Accepted
- Date: 2026-09-06

## Decision

- PostgreSQL 16 with the pgvector image is the relational source of truth.
- SQLAlchemy 2.x and Alembic 1.x provide async application access and migrations.
- Dramatiq with Redis 7 provides the worker boundary without coupling domain code to a queue SDK.
- MinIO provides an S3-compatible local object store; storage access is behind `StoragePort` and keys are tenant-prefixed.

M1 creates only identity tables. Artifact, SOP, draft, review and audit migrations are deferred to later milestones.
