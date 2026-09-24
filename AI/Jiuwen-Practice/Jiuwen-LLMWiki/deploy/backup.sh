#!/usr/bin/env bash
# E9-S6 / GL-O6: nightly backup — pg_dump of the gbrain Postgres + tarball of
# L1 sources, changesets, mirror and conversations. 14-day retention.
# Restore path is tested by deploy/restore-test.sh (same directory).
set -euo pipefail
PROJECT="/root/HuaweiCloudLatam_LLMWiki"
RUNTIME="$PROJECT/runtime"
OUT="${LLMWIKI_BACKUP_DIR:-$RUNTIME/backups}"
KEEP_DAYS=14
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT"

docker exec llmwiki_pg pg_dump -U llmwiki --no-owner --no-privileges -d llmwiki > "$OUT/gbrain-$STAMP.sql"
tar -C "$RUNTIME" -czf "$OUT/llmwiki-data-$STAMP.tar.gz" sources changesets wiki conversations 2>/dev/null \
  || tar -C "$RUNTIME" -czf "$OUT/llmwiki-data-$STAMP.tar.gz" sources changesets wiki
sha256sum "$OUT/gbrain-$STAMP.sql" "$OUT/llmwiki-data-$STAMP.tar.gz" > "$OUT/manifest-$STAMP.sha256"

find "$OUT" -name 'gbrain-*.sql' -mtime +"$KEEP_DAYS" -delete
find "$OUT" -name 'llmwiki-data-*.tar.gz' -mtime +"$KEEP_DAYS" -delete
find "$OUT" -name 'manifest-*.sha256' -mtime +"$KEEP_DAYS" -delete
echo "backup $STAMP ok: $(du -sh "$OUT/llmwiki-data-$STAMP.tar.gz" | cut -f1) data + gbrain sql"
