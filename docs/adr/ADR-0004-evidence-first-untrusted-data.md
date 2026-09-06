# ADR-0004: Evidence-First Untrusted Data

- Status: Accepted
- Date: 2026-09-06

## Decision

Treat documents, email text, spreadsheets, OCR text, SOP excerpts and model output as data, never as executable instructions. A proposed field is accepted only when its evidence reference points to the canonical parsed artifact and deterministic validation succeeds.

Store hashes, coordinates, excerpts where safe, provider/model/prompt/schema versions and concise decisions. Never store or display chain-of-thought.
