# AI-DLC — a spec-driven coding lifecycle for AI coding agents

AI-DLC turns an AI coding agent (Claude Code, and by extension any
shell-capable coding CLI — see `targets/`) into the **executor** of a
disciplined delivery flow, instead of a chat window you copy-paste from.
The agent reads the task, writes the code, and runs the tests itself,
inside a per-task git worktree. A spec validator checks that the change
is *well-formed*. A human reads the diff and holds the merge gate. That
division of labor — agent executes, tooling validates structure, human
judges correctness — is the whole architecture.

**Who this is for:** teams who want an AI agent doing real, mergeable
work in a real repo, with a paper trail (a signed spec verdict, a
delivery report, an approval with a rationale) instead of "the agent
said it was done."

**Prerequisites:** git, Python 3.10+, an OpenSpec-compatible spec
validator (installed automatically — see below), and a coding agent
that can run shell commands. The planning-plane features (multi-file
changes, adversarial design review, design-system-driven frontend work)
additionally need an `openjiuwen` gateway — see `install.sh --bootstrap`
for a guided, fresh-machine setup.

> **A note on names:** this document and most of the codebase refer to
> the gateway generically as **openjiuwen**. The installable package,
> its systemd service, and its config paths are named **`jiuwenswarm`**
> (e.g. `uv tool install jiuwenswarm`, the `jiuwenswarm-gateway` service,
> `~/.jiuwenswarm/`) — that's intentional, not an inconsistency: those
> are real identifiers a running system depends on, so `install.sh` and
> the code that talks to the gateway use the literal `jiuwenswarm` name
> throughout. Read `openjiuwen` and `jiuwenswarm` as the same gateway.

## Quick start

```bash
./install.sh --bootstrap   # fresh machine: dependencies, credentials, skills
./install.sh --doctor      # already set up? verify everything's healthy
```

Then, from your coding agent: read `supervisor/skills/claude/ai-dlc/SKILL.md`
(it's self-contained — L0 is enough to run a task) and ask the system
what to do next:

```bash
python3 bin/plan.py next --task-dir <task-dir> --repo <repo>
```

That single command is the whole manual. It returns the current stage,
what's blocking it, and the exact next command to run.

## How a task moves

```
ROUTE → WORK → [DESIGN] → CHECK → REPORT → MERGE_GATE
```

1. **ROUTE** — a 1–3 file, mechanical change goes **inline** (the
   default: the agent just does it). A 4+ file change, or one where
   reading the codebase *is* the work, goes to the **planning plane**:
   one role authors each change artifact, an adversarial review round
   checks the design before code is written, then implementation
   happens inline in the same task worktree. File count alone never
   picks the plane — risk and ambiguity do, and a human can always
   override the route.
2. **WORK** — the agent writes the code. Task descriptions specify
   *behavior*, never *shape* ("at least 4 modules," "layer it this
   way") — on a real benchmark, one shape-constraining sentence in a
   task description cost 12× the wall-clock time, 11× the input
   tokens, and made the result *less* correct, not more.
3. **DESIGN** *(web/deck surfaces only)* — a four-phase flow
   (**SELECT → SPECIFY → BUILD → VERIFY**) treats frontend design as a
   product the code must conform to, not an afterthought bolted onto
   finished pages. SELECT picks a design template from an indexed
   catalog by IDF-weighted retrieval (millisecond, no LLM call for the
   common case); SPECIFY turns it into concrete tokens/components/pages
   specs; BUILD writes pages against that spec; VERIFY runs six
   mechanical conformance checks. Design state is always visible at the
   merge gate — it never blocks a merge on its own.
4. **CHECK** — the spec validator runs `validate --strict` against the
   change; the signed verdict is read, never re-derived. Then the diff
   is presented for a human to read — that reading *is* the correctness
   check. No tool claims to verify correctness; only the two gates
   below (structural completeness, and a human's judgment) exist.
5. **REPORT / MERGE_GATE** — a delivery report measures the real git
   diff against the spec verdict and states plainly what was and
   wasn't checked. A human approves with a written rationale, or
   nothing merges — there is no auto-merge path. Approving runs the
   merge, archives the change, and cleans up the task branch and
   worktree; stopping without delivering leaves the target exactly as
   it was found (`plan.py sweep`).

Everything the agent's report shows a person distills to four states:
**Working → Checking → Ready | Needs your decision.**

## Two gates, and nothing else

- **G-DELIVER-1** — landed files/bytes measured from the actual git
  diff, plus the change passing the spec validator's `--strict` check.
  Structural only: it proves the change is well-formed, not that it's
  *right*.
- **MERGE_GATE** — a human, with a written rationale. The only gate
  that can say yes.

**Known trade-off, accepted deliberately:** no tool here judges whether
the implementation is *correct*, and there is no cost/budget gate —
usage is read from wherever it's already recorded (the agent's own
transcript, the gateway's session history), never computed or capped
here. A structurally broken deliverable produces no automatic alarm;
only a human who reads it catches that. This project chooses not to
build a second, worse verifier on top of a human's own judgment.

## Layout

- `supervisor/skills/claude/ai-dlc/SKILL.md` — the execution skill: the
  routing table, the four states, the hard prohibitions. This is the
  only file a running agent needs to read.
- `bin/report.py` — `init` / `deliver` / `gate`: the human-facing
  surface and both gates.
- `bin/plan.py` — the planning-plane dispatcher: one role per artifact,
  an adversarial design-review round, the D0–D3 design flow, boundary
  checks against a pre-run baseline, and `plan.py close` / `plan.py
  sweep` for the merge and rollback tails. Before any dispatch, the
  target repo is checked: a tree holding source this project must never
  modify is refused outright, and a partial working-tree checkout waits
  for a human's explicit acceptance.
- `config/collapsed.config.yaml` — the entire runtime configuration, 5
  keys.
- `targets/` — per-coding-agent install profiles. Claude Code gets a
  skill installed under its own config directory; other shell-capable
  agents (OpenAI Codex CLI, Cursor, GitHub Copilot's coding agent) get
  the same instructions packaged as `AGENTS.md` / Cursor project rules
  / Copilot instructions respectively — the underlying flow is identical
  for all of them, since `bin/plan.py` and `bin/report.py` are plain
  Python CLIs with no agent-specific coupling.
- `tests/collapse/` — the live test suite (shell + Python): the happy
  path, the spec-invalid negative, surface-measurement audits, the
  design-gate audit.
- `openspec/specs/` — the process's own spec definitions, validated the
  same way any tracked change is.
- `docs/` — design rationale and PRDs behind specific decisions. Not
  needed to run a task — only to understand *why* something works the
  way it does.

## Install / verify

```bash
./install.sh                  # skills + spec validator, for an already-set-up machine
./install.sh --bootstrap      # fresh machine: walks through every dependency,
                              # printing expected size/time before each step
./install.sh --setup-maas-key # interactive credential entry for the gateway
./install.sh --doctor         # health check: executables, validator smoke
                              # test, gateway reachability, credentials, design
                              # asset catalog
./install.sh --target codex   # install into a specific coding agent (see targets/)
```

## Constraints that don't expire

- Never modify the spec validator's or the gateway's source — not one
  line. This project depends on them; it doesn't fork or vendor them.
- Retiring code means a `git rm` plus a tag anchor in history, never a
  silent deletion — see the tags in this repo's git log for prior
  architecture generations this one replaced.
- No auto-merge. No shape constraints in task text. No code here judges
  an artifact "correct." No silent downgrade of failure into success.
  No cost/budget gate, cap, or advisory total — budgeting isn't
  provided upstream, and this project doesn't build one to fill the
  gap.

## License

MIT — see `LICENSE`.
