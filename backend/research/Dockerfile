FROM python:3.12-slim
WORKDIR /app
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt
COPY research/ research/
# Mount Cloud SQL at /cloudsql/<instance>, set DB_HOST to that directory.
# No schedule is installed by this image; operators explicitly enable the pilot.
CMD ["python", "-m", "research.cli", "run-once"]
