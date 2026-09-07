# 150-Second Synthetic Demo Script

This script is designed for a screen recording with no credentials and no
external service. The committed [demo.webm](assets/demo.webm) is a 150-second
synthetic local walkthrough; use the visual assets as a storyboard when the
local web shell is not running.

| Time | Action | Narration / proof |
| ---: | --- | --- |
| 0–15s | Open the queue and select `REQ-A-100`. | “This is a tenant-scoped synthetic intake queue.” |
| 15–35s | Select fields and show the highlighted source excerpt. | “Every accepted value remains tied to a verified evidence reference.” |
| 35–50s | Open the missing-field case. | “Missing required data blocks preview; the UI does not guess.” |
| 50–70s | Open the prompt-injection case. | “Instruction-like document text is data, not authority; preview is blocked.” |
| 70–88s | Correct a field and revalidate. | “An edit increments the review version and invalidates stale preview state.” |
| 88–108s | Create the immutable action preview. | “The payload is hash-bound to the draft, validation and review versions.” |
| 108–128s | Run `make demo-timeout-recovery`. | “A post-commit timeout is resolved by the same idempotency key and lookup.” |
| 128–142s | Show verified read-back and audit status. | “Completion requires the remote payload to match the approved action.” |
| 142–150s | Show the evaluation report. | “Scores are reproducible, synthetic and safety-gated.” |

## Recording commands

```bash
make demo-injection
make demo-timeout-recovery
make eval-fake
```

## Recording constraints

- Use only the committed synthetic fixtures and demo users.
- Keep API keys, tokens, document bodies and provider exception text out of the
  recording.
- Do not describe the system as autonomous, compliant or connected to a real
  OMS/WMS.
- If Docker is unavailable, record the deterministic web shell and CLI demo
  outputs, and identify the visuals as synthetic portfolio assets.
