# Hermes Setup Skill

Reproduce Hermes Agent configuration on a new Linux PC from a portable config directory.

## When to Use

- Setting up Hermes Agent on a new machine
- Reproducing an existing Hermes configuration elsewhere
- Troubleshooting a Hermes installation that doesn't match the reference setup

## Prerequisites

- Linux nativo (Ubuntu 24.04+ recommended)
- sudo access for installing system packages
- Internet connection for cloning repos and installing deps

## How to Run

```bash
# From the hermes-repro directory
cd ~/hermes-repro
./install.sh
```

The script is idempotent — safe to re-run. It skips steps that are already complete.

## Quick Reference

| Component | Location | Purpose |
|---|---|---|
| `install.sh` | `~/hermes-repro/` | Main orchestrator |
| `config/` | `~/hermes-repro/config/` | All config files with placeholders |
| `profiles/` | `~/hermes-repro/profiles/` | 7 profile configs |
| `README.md` | `~/hermes-repro/` | Full documentation |

## Procedure

1. Copy `~/hermes-repro/` to the target PC (USB, scp, git, etc.)
2. Run `./install.sh`
3. Replace all `PLACEHOLDER_*` values with real API keys
4. Configure Huawei MaaS as the LLM backend (set MAAS_API_KEY and MAAS_ENDPOINT env vars)
5. Run `hermes` or `hermes -p <profile>`

## Pitfalls

- **API keys**: All keys are placeholders. The script warns about remaining placeholders at the end.
- **Huawei MaaS**: Replace placeholder with your MaaS API key and endpoint from Huawei Cloud console.
- **Docker group**: After installing Docker, you may need to re-login for group permissions.
- **Python versions**: Hermes needs Python 3.11+. Installed automatically by the script.

## Verification

```bash
hermes --version                          # Should show v0.18.0+
curl -H "Authorization: Bearer $MAAS_API_KEY" $MAAS_ENDPOINT/v1/models  # Huawei MaaS
hermes -p finance chat "test"            # Profile test
grep -r "PLACEHOLDER_" ~/.hermes/ 2>/dev/null  # Should return nothing
```
