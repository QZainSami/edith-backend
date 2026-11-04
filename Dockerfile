FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY app.py emotion.py storage.py device_mailbox.py companion.py weather_service.py index.html ./
RUN useradd --create-home edith && mkdir -p /app/data && chown -R edith:edith /app
USER edith
ENV DEVICE_TRANSPORT=poll
EXPOSE 8000
CMD ["sh", "-c", "exec uv run --no-sync uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
