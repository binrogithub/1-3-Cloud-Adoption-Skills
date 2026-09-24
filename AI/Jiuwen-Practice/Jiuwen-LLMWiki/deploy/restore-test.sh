#!/usr/bin/env bash
# E9-S6: one tested restore. Loads the newest gbrain pg_dump into a THROWAWAY
# container (stock entrypoint, so POSTGRES_DB is created properly) and counts
# pages; unpacks the data tarball to a temp dir. Never touches the live llmwiki_pg.
set -euo pipefail
PROJECT="/root/HuaweiCloudLatam_LLMWiki"
OUT="${LLMWIKI_BACKUP_DIR:-$PROJECT/runtime/backups}"
SQL="$(ls -1t "$OUT"/gbrain-*.sql | head -1)"
TARBALL="$(ls -1t "$OUT"/llmwiki-data-*.tar.gz | head -1)"
TMP="$(mktemp -d)"
CID="restore-test-$$"
trap 'docker rm -f "$CID" >/dev/null 2>&1 || true; rm -rf "$TMP"' EXIT
docker run -d --name "$CID" --network llmwiki_net \
  -e POSTGRES_PASSWORD=restore-test -e POSTGRES_DB=restore_test pgvector/pgvector:pg16 >/dev/null
for i in $(seq 1 30); do docker exec "$CID" pg_isready -U postgres -d restore_test >/dev/null 2>&1 && break; sleep 1; done
docker exec "$CID" psql -U postgres -d restore_test -c "CREATE ROLE llmwiki LOGIN PASSWORD 'restore-test'" >/dev/null
docker exec -i "$CID" psql -U postgres -d restore_test -v ON_ERROR_STOP=1 < "$SQL" > "$TMP/restore.log" 2>&1
PAGES="$(docker exec "$CID" psql -U postgres -d restore_test -tAc 'SELECT count(*) FROM pages' 2>/dev/null || echo '?')"
CHUNKS="$(docker exec "$CID" psql -U postgres -d restore_test -tAc 'SELECT count(*) FROM content_chunks' 2>/dev/null || echo '?')"
tar -C "$TMP" -xzf "$TARBALL"
echo "restore test: sql=$(wc -l < "$SQL") lines; pages in dump: $PAGES; chunks: $CHUNKS; mirror pages: $(find "$TMP/wiki" -name '*.md' 2>/dev/null | wc -l)"
