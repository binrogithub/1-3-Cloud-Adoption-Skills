# Troubleshooting

## Repair Playbook

When fixing an existing deployment, follow this sequence:

1. **Inspect current state** — `docker compose ps`
2. **Inspect current config** — read `assets/config/litellm_config.yaml` (generated) and `.env` before editing
3. **Confirm environment** — verify `.env` contains real MaaS key(s) (not placeholders)
4. **Check DB connectivity** — `docker compose exec db pg_isready -d litellm -U llmproxy`
5. **Check LiteLLM health** — `curl -s http://localhost:4000/health -H "Authorization: Bearer $LITELLM_MASTER_KEY"`
6. **Fix the specific issue** — see Common failure modes below
7. **Restart if config changed** — `docker compose restart litellm`
8. **Re-validate** — run `scripts/validate_e2e.sh`

## Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `litellm` keeps restarting | DB not ready or wrong `DB_PASSWORD` | Check `docker compose logs db`, verify `.env` `DB_PASSWORD` |
| 401 from `/v1/chat/completions` | Wrong or missing API key | Verify `Authorization: Bearer sk-...` header |
| 404 model not found | Model name mismatch | Names are case-sensitive, must match MaaS console exactly |
| No metrics in Prometheus | LiteLLM healthcheck failing | Check `docker compose ps`, ensure litellm is healthy |
| `LITELLM_SALT_KEY` error | Salt changed after keys created | Use original salt; if lost, `docker compose down -v` and start fresh |
| MaaS 403 | Wrong region or expired key | Verify key in ModelArts console, region must be `ap-southeast-1` |
| Callback import error | `custom_callbacks.py` not mounted | Check volume mount in `docker-compose.yml` |
| `unhealthy_count > 0` in `/health` | Upstream model unreachable or rate-limited | Check MaaS key, model ID, and region |
| Budget not consumed on successful calls | Model has zero pricing | Set non-zero `input_cost_per_token` / `output_cost_per_token` |
| Prometheus target down | LiteLLM not healthy or not started | Check healthcheck chain: `db` → `litellm` → `prometheus` |
| Grafana shows no data | Prometheus not scraping or wrong datasource | Check Prometheus targets; verify datasource URL |
| Virtual key 403 | Key expired, over budget, or model not in allow-list | Check key with `/key/info` |
| Error Rate shows 0% when failures exist | Label mismatch on deployment metrics | Dashboard must use `{litellm_model_name=~"$model"}` for deployment metrics |
| Partial degradation (some deployments cooldown) | One MaaS API key expired or rate-limited | Check cooldown events in Grafana; identify and rotate failed key |
| Uneven request distribution | Routing strategy not optimal | Consider `least-latency` strategy; check per-deployment latency in Grafana |
| Config file overwritten | Edited `litellm_config.yaml` directly | Edit `litellm_config.yaml.example` instead; run `generate_config.sh` |
| Deployment count mismatch | `HUAWEI_MAAS_API_KEY_COUNT` wrong | Verify count matches indexed keys in `.env`; regenerate config |
| One MaaS key expired | Some deployments in cooldown, partial degradation | Replace expired key in `.env`, re-run `generate_config.sh`, restart litellm |
| Uneven request distribution | Routing strategy not optimal | Try `--routing-strategy=least-busy` or `latency-based-routing` |
| `litellm_config.yaml` not found | Config not generated | Run `scripts/generate_config.sh` |
| Deployment count mismatch | `.env` keys changed without regenerating config | Re-run `scripts/generate_config.sh`, restart litellm |
| Intermittent TimeoutError | `request_timeout` too low — LLM calls exceed timeout end-to-end (not just TTFT) | Increase `request_timeout` to 600s (default); add `stream_timeout: 60` for TTFT deadline |

## Common Mistakes

| Mistake | Why it's wrong | Correct approach |
|---|---|---|
| Committing `.env` to git | Leaks all secrets | `.env` is gitignored; never `git add .env` |
| Changing `LITELLM_SALT_KEY` after creating virtual keys | All existing keys become unreadable | Keep the original salt; if lost, full reset required |
| Giving clients the raw `HUAWEI_MAAS_API_KEY` | Bypasses spend tracking, rate limiting, and audit | Mint virtual keys via `/key/generate` |
| Using per-1K-token pricing in `model_info` | LiteLLM expects per-token pricing | Use `input_cost_per_token` (e.g. `0.000001078`) |
| Adding a model with zero pricing | Budgets don't consume spend | Always set non-zero `input_cost_per_token` and `output_cost_per_token` |
| Guessing model names | MaaS model IDs are case-sensitive | Verify exact name in MaaS console before adding |
| Editing `assets/config/litellm_config.yaml` directly | File is regenerated and overwritten | Edit `litellm_config.yaml.example` and run `generate_config.sh` |
| Editing config without restarting | Config is read at startup only | `docker compose restart litellm` after any config change |
| Running `docker compose down` and expecting data loss | Volumes survive `down` | Use `docker compose down -v` to destroy data |
| Checking `/health/liveliness` instead of `/health` for model status | Liveliness only checks process | Use `/health` with auth for model-level diagnostics |
| Non-contiguous key indices | Gaps in `HUAWEI_MAAS_API_KEY_N` cause issues | Keys must be 0, 1, 2... without gaps |
| Changing `.env` keys without regenerating config | Config still references old key count | Always run `generate_config.sh` after `.env` changes |
| Setting `request_timeout` too low (e.g. 10s) | LLM calls routinely exceed 10s end-to-end, causing intermittent TimeoutErrors | Use `request_timeout: 600` (default); use `stream_timeout` for tighter TTFT control |

## Sanitization Rules

- **Never write real API keys, virtual keys, bearer tokens, or database passwords into committed files.** Use `.env` (gitignored) with `0600` permissions.
- **In generated output or documentation**, use placeholders: `sk-<master-key>`, `<maas-api-key>`, `<db-password>`.
- **When demonstrating configuration**, read secrets from environment variables, never hardcode.
- **Mask discovered keys** as `<prefix>...<suffix> (len=N)` or `***redacted***` in logs and debug output.
- **LiteLLM may print custom `api_key` values in startup logs.** Scan and scrub: `docker compose logs litellm 2>&1 | grep -i 'api_key\|sk-'`.
