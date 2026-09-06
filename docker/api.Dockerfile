FROM python:3.12-slim

WORKDIR /workspace
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

COPY pyproject.toml ./
RUN pip install --no-cache-dir uv==0.12.2
COPY . .
RUN uv sync --dev

CMD ["uv", "run", "--no-sync", "uvicorn", "apps.api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
