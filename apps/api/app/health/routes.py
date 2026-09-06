import httpx
from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import text

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(request: Request) -> dict[str, str]:
    checks: dict[str, str] = {}
    session_factory = request.app.state.session_factory
    try:
        async with session_factory() as session:
            await session.execute(text("select 1"))
        checks["database"] = "ok"
    except Exception:  # pragma: no cover - exact driver errors vary by environment
        checks["database"] = "error"

    try:
        await request.app.state.redis_client.ping()
        checks["redis"] = "ok"
    except Exception:  # pragma: no cover - external service is optional in unit tests
        checks["redis"] = "error"

    try:
        endpoint = request.app.state.settings.object_storage_endpoint.rstrip("/")
        async with httpx.AsyncClient(timeout=1.0) as client:
            response = await client.get(f"{endpoint}/minio/health/live")
        checks["object_storage"] = "ok" if response.is_success else "error"
    except Exception:  # pragma: no cover - external service is optional in unit tests
        checks["object_storage"] = "error"

    if all(value == "ok" for value in checks.values()):
        return {"status": "ok", **checks}
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail={"status": "not_ready", **checks}
    )
