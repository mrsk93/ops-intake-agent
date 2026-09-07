from __future__ import annotations

import asyncio
import json
from typing import Any

from packages.domain.artifacts import content_sha256
from packages.testkit.fakes import MockOperations


async def _run_demo() -> dict[str, Any]:
    operations = MockOperations(timeout_after_commit_once=True)
    payload = {
        "external_request_reference": "REQ-A-RECOVERY",
        "line_items": [{"sku": "SKU-100", "quantity": 2, "unit": "EA"}],
    }
    tenant_id = "tenant-a"
    idempotency_key = content_sha256(b"tenant-a:REQ-A-RECOVERY:payload-v1")

    try:
        await operations.create_draft(
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
            payload=payload,
            correlation_id="demo-timeout-1",
        )
    except TimeoutError:
        pass

    found = await operations.lookup(tenant_id=tenant_id, idempotency_key=idempotency_key)
    if found is None:
        raise RuntimeError("synthetic lookup did not find the committed draft")
    readback = await operations.read_back(tenant_id=tenant_id, remote_id=found["remote_id"])
    verified = (
        readback["tenant_id"] == tenant_id
        and readback["idempotency_key"] == idempotency_key
        and readback["payload_sha256"] == found["payload_sha256"]
    )
    return {
        "status": "verified_after_lookup" if verified else "manual_exception",
        "create_calls": operations.create_calls,
        "remote_record_count": len(operations.records),
        "read_back_verified": verified,
    }


def run_demo() -> dict[str, Any]:
    return asyncio.run(_run_demo())


def main() -> None:
    result = run_demo()
    print(json.dumps(result, sort_keys=True))
    if result["status"] != "verified_after_lookup" or result["remote_record_count"] != 1:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
