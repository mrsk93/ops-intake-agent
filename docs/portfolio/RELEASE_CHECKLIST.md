# M12 Portfolio Release Checklist

- [x] README explains fake-only quickstart, trust boundaries and limitations.
- [x] Data-flow diagram documents the model, review and operations boundaries.
- [x] Model card states intended use, out-of-scope use, synthetic provenance and
      limitations.
- [x] Evaluation report links the committed JSON result and reproduction command.
- [x] Demo reset/injection/timeout stories use deterministic synthetic fakes.
- [x] Six synthetic visual assets cover review, blocking, injection, preview,
      recovery and evaluation states.
- [x] Six browser PNG captures are included for the review, blocking, injection,
      preview, recovery and evaluation states.
- [x] A 150-second synthetic WebM walkthrough is committed at
      `docs/portfolio/assets/demo.webm`.
- [x] Fresh-clone `make release-check` rehearsal is documented and executable.
- [x] No real client data, credentials, prompts or chain-of-thought are stored.
- [x] No autonomous or compliance claim is made.
- [x] M0–M11 checks remain in the full test/lint/evaluation gate.
- [x] Release tag is created only after the final checks pass.
