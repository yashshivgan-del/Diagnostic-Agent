# Build from the repository root:  docker build -f backend/Dockerfile -t pda-backend .
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY simulator simulator
COPY backend backend
COPY tools tools
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1
EXPOSE 8000
# One worker: run workers and the live-update listener live in this process.
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
