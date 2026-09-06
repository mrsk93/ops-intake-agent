import dramatiq


@dramatiq.actor
def health_task() -> str:
    """M1 no-op task proving the worker boundary is wired without side effects."""
    return "ok"
