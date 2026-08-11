FROM python:3.9-slim

WORKDIR /app
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# We only need api/ for the Cloud Run deployment, but we might need ingestion/utils.py if we depend on it.
# Actually, the api doesn't import from ingestion.
COPY api/ api/

ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
