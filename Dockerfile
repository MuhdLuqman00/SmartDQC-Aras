FROM python:3.12-slim

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY data/zscore/ ./data/zscore/
COPY alembic.ini ./alembic.ini
COPY alembic/ ./alembic/
COPY scripts/entrypoint.sh ./entrypoint.sh

RUN chmod +x ./entrypoint.sh

ENV WHO_ZSCORE_DIR=/app/data/zscore
ENV OLLAMA_BASE_URL=http://ollama:11434

EXPOSE 8000
CMD ["./entrypoint.sh"]
