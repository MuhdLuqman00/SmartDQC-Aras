#!/bin/bash
set -e

# Add postgres binaries to PATH (Ubuntu installs them version-specific)
PG_BIN=$(find /usr/lib/postgresql/*/bin -maxdepth 0 2>/dev/null | sort -V | tail -1)
export PATH="$PG_BIN:$PATH"

PGDATA=/var/lib/postgresql/data
POSTGRES_USER=${POSTGRES_USER:-smartdqc}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-smartdqc}
POSTGRES_DB=${POSTGRES_DB:-smartdqc}

# Initialise postgres data dir on first boot
if [ ! -f "$PGDATA/PG_VERSION" ]; then
    echo "[init] Initialising PostgreSQL..."
    mkdir -p "$PGDATA"
    chown postgres:postgres "$PGDATA"
    su postgres -c "initdb -D $PGDATA"
fi

# Start postgres (managed here so migrations can run before api starts)
su postgres -c "pg_ctl start -D $PGDATA -w -l $PGDATA/postgresql.log"

# Create role and database if they don't exist
su postgres -c "psql -tc \"SELECT 1 FROM pg_roles WHERE rolname='$POSTGRES_USER'\" | grep -q 1 \
    || psql -c \"CREATE USER $POSTGRES_USER WITH PASSWORD '$POSTGRES_PASSWORD';\""
su postgres -c "psql -tc \"SELECT 1 FROM pg_database WHERE datname='$POSTGRES_DB'\" | grep -q 1 \
    || psql -c \"CREATE DATABASE $POSTGRES_DB OWNER $POSTGRES_USER;\""

# Run Alembic migrations
echo "[init] Running migrations..."
cd /app
DATABASE_URL="postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost/$POSTGRES_DB" \
    alembic -c /app/alembic.ini upgrade head

# Pull ollama model in background once ollama is up
(
    until curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; do sleep 3; done
    echo "[init] Verifying Ollama model: ${OLLAMA_MODEL:-hf.co/mradermacher/gemma-4-E4B-GGUF:Q6_K}"
    curl -s http://localhost:11434/api/pull -d "{\"name\":\"${OLLAMA_MODEL:-hf.co/mradermacher/gemma-4-E4B-GGUF:Q6_K}\"}" | tail -1
    echo "[init] Model ready."
) &

exec /usr/bin/supervisord -n -c /etc/supervisor/conf.d/smartdqc.conf
