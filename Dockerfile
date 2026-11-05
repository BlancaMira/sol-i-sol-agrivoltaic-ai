# Lightweight, read-only preview of the original dashboard with a curated data subset.
FROM python:3.11-slim
WORKDIR /app
COPY dashboard/ /app/dashboard/
EXPOSE 8501
CMD ["python", "-m", "http.server", "8501", "--directory", "/app/dashboard"]
