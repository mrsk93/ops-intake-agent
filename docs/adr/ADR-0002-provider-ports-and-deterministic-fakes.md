# ADR-0002: Provider Ports and Deterministic Fakes

- Status: Accepted
- Date: 2026-09-06

## Decision

Define provider-neutral protocols for classification, extraction, OCR, storage and operations. Application code depends on these ports, not SDK clients. Deterministic fakes live in `packages/testkit` and are the default CI/demo path.

The model provider receives bounded evidence and schema/prompt versions only. It receives no operations credentials, authorization context, or direct operational tool. CI must remain valid with no API key and no hosted provider.

## Consequences

Live provider adapters can be added later without changing domain policy or test fixtures. Provider responses remain untrusted and require schema and deterministic validation before entering canonical state.
