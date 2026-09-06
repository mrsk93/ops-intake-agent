# ADR-0009: Structured Extraction Provider Boundary

- Status: Accepted
- Date: 2026-09-06

## Decision

Model classification and extraction are provider-port operations that return
untrusted mappings. The application validates them locally against strict
Pydantic models, verifies every evidence coordinate and excerpt against the
supplied parsed material, and rejects unsupported field paths before canonical
state is built.

The deterministic fake may select outputs by an evidence-content hash and can
simulate refusal, timeout and invalid-output cases. CI uses this fake and does
not require an API key.

The optional OpenAI adapter uses the current Responses API JSON Schema contract
under `text.format`, passes no operational tools, and defaults `store=False`.
Provider refusals and incomplete responses become explicit reviewable run
statuses. Provider/model/prompt/schema versions, request IDs, hashes, latency
and token metadata are retained; raw model output and hidden reasoning are not
persisted by the extraction service.

## Consequences

- Provider SDKs stay outside the domain package.
- A schema-valid response is still not trusted until evidence and field-path
  checks pass.
- Live-provider behavior is opt-in and must be reverified when the official API
  contract or SDK version changes.

## Official baseline checked

The current OpenAI Structured Outputs guide and Responses create reference were
accessed on 2026-09-06. They document `responses.create` with
`text.format.type=json_schema`, strict schemas, separate refusal output and the
`store` retention flag. See ADR-0001 for the complete source list.
