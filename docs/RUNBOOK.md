# Portfolio Runbook

The maintained failure, retention and backup/restore guidance is in
[OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md). This page is the short release
entry point for the fake-only portfolio rehearsal.

## No-credential rehearsal

```bash
cp .env.example .env
uv sync --dev
pnpm install --frozen-lockfile
make release-check
```

`make release-check` runs the release tree check, full tests, lint/type checks,
the fake evaluation, repository security scan and both deterministic demo
stories. It does not call a hosted model or an operations system.

## Demo stories

```bash
make demo-injection
make demo-timeout-recovery
```

The first prints a blocked prompt-injection fixture with zero operational
writes. The second simulates a timeout after remote commit, finds the existing
record by the same idempotency key and verifies it by read-back.

## Operational boundaries

- Do not point reset commands at a non-demo database or bucket.
- Do not add real documents or credentials to fixtures, logs or screenshots.
- Keep provider credentials outside the model boundary.
- Treat any uncertain operation as recoverable/uncertain until lookup and
  read-back agree with the immutable preview.
- Use the full [operations runbook](OPERATIONS_RUNBOOK.md) for failure-class
  handling, retention and production adaptation notes.
