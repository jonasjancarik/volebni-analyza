# Frontend of the new app (web/), built into static files
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

COPY streamlit_app.py ./
COPY src ./src
COPY .streamlit/config.toml ./.streamlit/config.toml
COPY --from=web /web/dist ./web/dist

# The image serves the new app; docker-compose.yml overrides the command for
# the original Streamlit app.
EXPOSE 8600 8501
CMD ["uv", "run", "--no-sync", "uvicorn", "--app-dir", "src", "web_api:app", \
     "--host", "0.0.0.0", "--port", "8600"]
