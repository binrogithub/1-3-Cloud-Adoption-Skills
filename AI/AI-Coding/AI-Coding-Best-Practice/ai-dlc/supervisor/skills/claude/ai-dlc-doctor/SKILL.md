---
name: ai-dlc-doctor
description: Health check for the collapsed AI-DLC runtime — run ./install.sh --doctor from the repo root. Verifies an install or debugs the two gates.
version: "0.9"
---

# AI-DLC Doctor

`./install.sh --doctor` checks: bin/report.py and bin/plan.py present,
config present, the environment's validator discriminates (the smoke
runs it host-side — a valid change passes `--strict`, a scenario-less
requirement is rejected; inside a run the caller reads verdicts only as
signed records), and the planning dispatch can reach the gateway — the client it invokes, the
service it talks to, the config that service reads. No cost or budget
gate is checked; none exists. Exit 0 healthy, 1 a check failed.
