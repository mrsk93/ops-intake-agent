# Ops Intake Agent Data Flow

This diagram describes the M0–M12 synthetic demonstration. It is a design
and review aid, not a claim that the local Compose stack is production-ready.

```mermaid
flowchart LR
    U["Tenant user"] -->|Bearer token + membership| API["FastAPI API"]
    DOC["Untrusted email / PDF / image / table"] --> Q["Quarantine storage"]
    API --> Q
    Q --> P["Deterministic parse + evidence map"]
    P --> OCR["OCR port when needed"]
    P --> X["Schema-constrained classification / extraction"]
    X --> V["Evidence verification + canonical validation"]
    SOP["Approved tenant SOP versions"] --> R["Tenant-filtered retrieval"]
    R --> V
    V --> REV["Review state + immutable draft version"]
    REV --> INT["Human review interrupt"]
    INT --> PRE["Immutable action preview"]
    PRE --> AUTH["Current authorization + revalidation"]
    AUTH --> OPS["Mock operations port"]
    OPS --> LOOK["Lookup / read-back verification"]
    LOOK --> AUD["Safe audit timeline"]
    API --> AUD
```

## Trust boundaries

| Boundary | Rule |
| --- | --- |
| Upload → parser | Bytes, OCR text and embedded text are data, never instructions. |
| Parser → model | Only bounded evidence is supplied; schema and evidence references are explicit. |
| Model → canonical state | Strict output validation, evidence verification and tenant master-data checks run first. |
| Canonical state → action | The preview is immutable and bound to the current draft, validation and review versions. |
| Approval → operations | Authorization and policy are rechecked immediately before the mock adapter call. |
| Operations → completion | A receipt is not sufficient; lookup/read-back must match the approved payload. |

The model has no operational credentials and no operation-tool definition.
Standard logs retain IDs, hashes, versions, timings and safe decisions—not
document text, prompts or chain-of-thought.
