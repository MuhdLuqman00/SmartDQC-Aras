FROM python:3.12-slim

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

ENV WHO_ZSCORE_DIR=/app/data/zscore
ENV SMARTDQC_DB_PATH=/app/data/smartdqc.duckdb
ENV OLLAMA_BASE_URL=http://ollama:11434

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
