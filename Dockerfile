# Frontend (web/), built into static files
FROM node:24-bookworm-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Dependencies first, so that code changes do not reinstall them
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY --from=web /web/dist ./web/dist

EXPOSE 8600
CMD ["uv", "run", "--no-sync", "uvicorn", "--app-dir", "src", "web_api:app", \
     "--host", "0.0.0.0", "--port", "8600"]
