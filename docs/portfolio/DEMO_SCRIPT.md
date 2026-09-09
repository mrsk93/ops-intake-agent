# 120-Second Synthetic Product Demo Script

This is a voiceover-ready script for the committed [demo.webm](assets/demo.webm).
The video is a silent screen recording of the local provider-free web shell; the
narration below can be recorded separately for a polished product walkthrough.
Everything shown is synthetic and read-only.

## Story

The story is simple: an operations reviewer takes one intake request from
untrusted document text to a safe, immutable preview. The system earns each
step with evidence, deterministic checks and an explicit human decision.

| Time | On-screen action | Voiceover |
| ---: | --- | --- |
| 0–10s | Hold on the control-desk opening view. | “Most intake systems make the risky part look invisible. Ops Intake puts the evidence, the draft and the release gate in one place.” |
| 10–25s | Show the synthetic queue and open `REQ-A-100`. Scroll into the three-panel workspace. | “This is a tenant-scoped synthetic queue. We start with one request, one reviewer and one current draft version.” |
| 25–40s | Select a canonical field and show its highlighted source excerpt. | “Every accepted value stays attached to a source excerpt. The model can extract and classify, but it never receives an operational credential or calls a tool.” |
| 40–52s | Open `REQ-A-101` and show the missing postal code with the disabled preview. | “When required evidence is missing, the system stops. It does not fill the gap with a guess, and it cannot compose an action preview.” |
| 52–68s | Open `REQ-A-102` and show the instruction-like handling note. | “Now the adversarial case: instruction-like text is rendered as untrusted data. It is not authority, and the policy gate blocks the request.” |
| 68–83s | Return to `REQ-A-100`, edit the quantity, and save the correction. | “A reviewer can correct a field, but the correction creates a new draft version. Any stale preview is invalidated and the evidence trail remains visible.” |
| 83–101s | Scroll to the release gate and create the immutable preview. | “Only after deterministic validation passes can we create a preview. Its hash binds the payload to the draft, validation and review version.” |
| 101–114s | Hold on the preview confirmation. | “This is still not an operational write. It is a reviewable, immutable proposal waiting for explicit approval.” |
| 114–120s | Close on the complete workspace. | “The design goal is not autonomous action. It is faster review with a smaller blast radius and a clear reason for every decision.” |

## Presenter notes

- Emphasize the transition from **document** to **draft** to **preview**.
- Pause on the missing-field and prompt-injection states; those are the safety
  proof points, not edge-case decoration.
- Say “synthetic” and “provider-free” on camera. Do not imply connection to a
  real OMS, WMS, customer, account or production workflow.
- Keep the final sentence focused on bounded assistance and human control.

## Reproduce the supporting proof

```bash
make demo-injection
make demo-timeout-recovery
make eval-fake
```

These commands provide the companion CLI proof for injection blocking,
idempotent timeout recovery and reproducible synthetic evaluation. They are not
required to play the browser video.

## Recording constraints

- Use only committed synthetic fixtures and demo users.
- Keep API keys, tokens, document bodies and provider exception text out of the
  recording.
- Do not describe the system as autonomous, compliant or connected to a real
  OMS/WMS.
- If Docker is unavailable, record the deterministic web shell and CLI proof,
  and identify the visuals as synthetic portfolio assets.
