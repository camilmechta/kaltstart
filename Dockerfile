# The Kaltstart web app. Any host that runs a container can serve it; the
# configuration comes from environment variables (see the README).
FROM python:3.12-slim
WORKDIR /app
# Exact versions first, so a new release of a library never changes the app
# by surprise; then the app itself, without touching them.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --no-deps .
# The app never runs as root.
RUN useradd --create-home --uid 10001 kaltstart
USER kaltstart
ENV PORT=8000
# PROXY_HOPS: how many proxies of the host stand in front of the app (1 on
# most hosts); the app reads the client's address from the entry they add.
ENV PROXY_HOPS=1
# No access log: requests are not logged one by one; errors are, without data.
CMD uvicorn --factory kaltstart.api.app:app_from_env --host 0.0.0.0 --port "$PORT" \
    --no-access-log
