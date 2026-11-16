# The Kaltstart web app. Any host that runs a container can serve it; the
# configuration comes from environment variables (see the README).
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
ENV PORT=8000
# No access log: requests are not logged one by one; errors are, without data.
CMD uvicorn --factory kaltstart.api.app:app_from_env --host 0.0.0.0 --port "$PORT" \
    --no-access-log --proxy-headers --forwarded-allow-ips="*"
