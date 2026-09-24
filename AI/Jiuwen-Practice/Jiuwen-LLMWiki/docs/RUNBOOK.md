# LLMWiki runbook (E9-S7 / GL-O7)

Host: 247 (`/root/HuaweiCloudLatam_LLMWiki`). Everything runs as root under systemd.

## Services

| Unit | What | Notes |
|---|---|---|
| `llmwiki-jiuwen-agentserver` | dedicated JiuwenSwarm agentserver (:20092) | stock binary, isolated data dir |
| `llmwiki-jiuwen-gateway` | dedicated gateway (:20001 WS / :20000 web) | Requires= agentserver |
| `llmwiki-web` | glue web UI/API (:20080) | front with Caddy for TLS (E11-S5) |
| `llmwiki-lint.timer` | nightly lint + reverify at 02:30 | writes `_meta/lint-report-<date>` |
| `llmwiki-backup.timer` | nightly backup at 01:30 | `runtime/backups/`, 14-day retention |
| Docker `llmwiki_pg` | gbrain Postgres + pgvector (:25432, localhost only) | own network `llmwiki_net`; NEVER `litellm_pg_db` |
| Docker `llmwiki_embed` | TEI embedding server (:20081, localhost only) | e5-small, ADR-001 |

## Start / stop / status

```bash
systemctl status llmwiki-jiuwen-agentserver llmwiki-jiuwen-gateway llmwiki-web
systemctl restart llmwiki-web
journalctl -u llmwiki-jiuwen-gateway -f
docker logs -f llw 2>/dev/null || docker logs -f llmwiki_pg
```

**Never `pkill -f jiuwenswarm`** — the pattern matches the calling shell's own
command line and kills your session, and it would also hit the SHARED instance
(`jiwenswarm-*` units on 19000/18092) that other projects depend on. Always stop by
unit name or PID from `systemctl show -p MainPID <unit>`.

## Health / diagnostics

```bash
./bin/llmwiki doctor          # binaries, instance, .env, workdir, gateway, gbrain engine, embeddings
curl -s localhost:20080/health | jq           # version + git SHA (AG-8)
curl -s localhost:20080/metrics | head        # Prometheus text
./bin/llmwiki lint --json | jq
deploy/resource_check.sh      # NFR-4 budget vs neighbours
```

## Recovering the wiki from the mirror (D-6)

Every gbrain write is mirrored to `runtime/wiki/*.md`. If the brain DB is lost:

```bash
docker exec llmwiki_pg psql -U llmwiki -d llmwiki -c '\dt'   # inspect
deploy/restore-test.sh                                       # verify newest backup first
# then re-import the mirror:
gbrain import runtime/wiki --no-embed && gbrain embed --stale
```

## Secrets

- MaaS key: `runtime/jiuwen/config/.env` (0600, gitignored). Dedicated key pending
  ADR-002 execution; currently the shared key copied by the installer.
- API tokens: `runtime/auth/tokens.json` (hashed). Mint with
  `./bin/llmwiki token --role curator --name <name>` (printed once).

## Known-bad actions

- `docker restart` on `litellm_pg_db` or any `latam_ai_workbench-*` container —
  neighbour property (NFR-5).
- Editing `~/.jiuwenswarm/` — that is the shared instance's home.
- Writing wiki pages by hand — the only write path is approved change sets (D-5),
  except `_meta/` operational pages written by the glue.
