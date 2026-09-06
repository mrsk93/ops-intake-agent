# M0/M1 Threat Model

## Assets

Tenant membership, authentication tokens, future document content, provider outputs, audit metadata and operational action authorization.

## Threats and controls

| Threat | Control in M0/M1 |
| --- | --- |
| Cross-tenant data access | Tenant ID is required in repository queries; membership is checked for every request. |
| Forged/expired token | JWT signature and expiry validation; user and membership status are re-read from the database. |
| Demo configuration used in production | Production settings reject demo controls, fake providers and the default JWT secret. |
| Model/provider credential misuse | Provider protocols separate extraction from operations; no live model adapter or operations endpoint exists in M1. |
| Destructive reset against the wrong system | Reset requires explicit confirmation, development mode, approved database name and exact demo bucket. |
| Untrusted instructions in documents | Evidence/model boundaries are documented; no document is executed as code. |

Residual risk: Docker image and dependency supply-chain verification, file scanning, artifact retention and operational approval gates are later-milestone work.
