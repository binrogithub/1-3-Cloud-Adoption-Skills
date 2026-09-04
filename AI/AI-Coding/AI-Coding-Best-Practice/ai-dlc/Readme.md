# AI-DLC-DevTeam

**A team of collaborating AI agents that raises the quality of AI-written code —
built on Openjiuwen and Jiuwenswarm.**

AI-DLC-DevTeam is a spec-driven development runtime in which AI coding agents work
like a real engineering team — a planner, an author, a UI designer, adversarial
reviewers, a spec validator and an archiver — each in its own isolated session,
every artifact measured and signed, and **a human holding the merge gate**. Quality
comes from the collaboration structure: specialization, adversarial review, strict
spec validation, and measurement instead of self-reporting.

> Core belief, learned from measurement: an orchestrator that delegates everything
> and verifies nothing does not scale (a 9,670-line delegation plane went 0-for-4
> on correct deliveries while burning ~5M input tokens — the full account is in
> `CHANGELOG.md`). What works is a collapsed runtime: agents do the work, machines
> check structure, and a person reads the diff.

---

## Built on Openjiuwen + Jiuwenswarm

The team is not an abstraction — it runs on two concrete pieces of infrastructure,
used read-only and never modified:

### Jiuwenswarm — the agent gateway

**Every role on the team is dispatched through the Jiuwenswarm gateway.** It is a
systemd-sandboxed gateway service (`jiuwenswarm-gateway`) that opens one fresh
agent session per role:

```bash
jiuwenswarm chat "You are the UI Designer for the delivery '<change>'…" \
    --jsonl --cwd <worktree>
```

- **One session per role** — the planner, author, ui-designer, each reviewer, the
  validator, the archiver and the codegraph builder each get a fresh, isolated
  session with its own event frames on disk (`~/.jiuwenswarm/agent/sessions/`).
  Nothing shares context that should not be shared.
- **Frames are the evidence** — a dispatch's facts are judged from the session's
  recorded frames, not from the agent's self-report. A role that claims work it
  did not do fails the dispatch.
- **A real agent runtime, not a thin wrapper** — jiuwenswarm sessions carry the
  full tool set, including a built-in **Task tool for subagent dispatch**
  (`subagent_type`/`description`/`prompt`, matching Claude Code's own schema),
  which the codegraph role uses to fan out named sub-agents
  (`project-scanner`, `file-analyzer`, `architecture-analyzer`, …).
- **Sandboxed by systemd** — the gateway unit's `ReadWritePaths` confines writes
  to the plane's home and the workspace; design references are `ReadOnlyPaths`
  bind mounts that bite even root.

### Openjiuwen — the agent core

**Openjiuwen is the agent-core framework underneath the gateway.** It provides the
session runtime the roles actually run in: model clients, tool execution, and the
memory/persistence layer (SQLite / key-value / vector stores as configured in the
gateway's `openjiuwen` section). AI-DLC-DevTeam treats it the way a good team
treats its platform: it builds *on* it, and its efficiency is itself improved
through the same gated workflow (a multi-phase `openjiuwen agent-core efficiency
optimization` initiative already ran through `plan.py initiative`).

### Why this matters for quality

Because specialization is enforced by infrastructure, not by prompt-politeness:
a role is a Jiuwenswarm session with a narrow mandate, judged from frames, writing
inside a boundary baseline. A reviewer cannot silently edit the design; a designer
cannot skip reading its pinned reference; the author cannot validate its own spec —
the validator is a different session reading the same signed records.

---

## Main features

- **Spec-driven lifecycle** — every task walks `ROUTE → WORK → DESIGN → REVIEW →
  CHECK → REPORT → MERGE_GATE`, with state recorded under `.ai-dlc/tasks/<task_id>/`.
- **Role-based agent team over Jiuwenswarm** — one role per artifact (proposal,
  design, specs, validation, UI design, review, archive), each dispatched into its
  own fresh gateway session. Every conclusion lands as a **signed record** — the
  caller reads records, it never re-runs the tool.
- **Two gates, nothing else** —
  `G-DELIVER-1`: the landed files/bytes from the real `git diff`, plus the change
  passing `openspec validate --strict`;
  `MERGE_GATE`: a human approves with a written rationale. **No auto-merge, ever.**
- **Adversarial review round** — reviewers each hold exactly one axis and one
  antagonistic persona, file at most one finding each (or an explicit
  nothing-found), and the executor synthesizes the findings itself.
- **Design as a product** — a UI-designer role works against a pinned, read-only
  OpenDesign reference (digest-pinned; a moved tree stops the dispatch before a
  session opens), with SELECT→SPECIFY→BUILD→VERIFY stages and four honest deliver
  states (`designed / design_unverified / design_skipped / not_applicable`).
- **Worktree-per-task isolation** — work happens in `git worktree` branches
  (`task/<id>`); nothing touches the main branch except through the merge gate.
- **Resume, not restart** — re-entering planning skips artifacts already done and
  continues a role's own named session; work already paid for is never paid for
  again.
- **Structure-first planning (codegraph)** — before the author dispatch, a
  codegraph role builds a code-structure graph (Understand-Anything backend,
  fanned out through Jiuwenswarm's Task tool) and produces an impact brief, so
  planning starts from the real dependency structure.
- **Phase-chain automation** — `plan.py initiative register/advance/status`
  chains multi-phase initiatives through the same gate discipline.
- **Honesty rules that bite** — a live result is not `delivered`; gate approvals
  and skips must name a human (`--approver <name>` — a model name is refused);
  internal contradictions in a delivery report fail the delivery instead of being
  written to disk.

## Repository layout

```
├── bin/plan.py          planning dispatch: roles, validate, design, review, close, next…
├── bin/report.py        delivery measurement, gate presentation, four deliver states
├── install.sh           multi-target installer (--doctor, --provision-plane, --uninstall)
├── SKILL.md             the agent-facing entry point (first screen is self-contained)
├── config/              collapsed.config.yaml (planning threshold, review axes, …)
├── openspec/            spec templates + archived changes (strict validation target)
├── docs/                PRDs — every change starts as one, decisions and evidence included
├── supervisor/          runtime supervision skills
├── targets/             install target definitions (claude, codex, cursor, copilot, …)
├── scripts/             installer helper scripts
├── tests/               the measured test suite
├── CHANGELOG.md         every version entry carries its measurements
└── LICENSE
```

## How to use

### 1. Install

```bash
git clone <this-repo> && cd ai-dlc
./install.sh                      # default target (Claude Code skill)
./install.sh --target codex      # a specific registered target (see targets/)
./install.sh --doctor            # health check: tools present, validator discriminates,
                                 # jiuwenswarm gateway reachable, sha256 consistency
./install.sh --provision-plane   # open the plane runtime (idempotent; scripted, probed)
```

`--doctor` verifies the whole chain the team runs on: the plane tools, a validator
that actually discriminates (a valid change passes `--strict`, a scenario-less one
is rejected), and a live probe **through the Jiuwenswarm gateway** — client,
service, and the config that service reads.

### 2. Run a task

Ask your coding agent to invoke the **`ai-dlc`** skill with the task description —
that is the intended entry point. The agent drives the flow; `plan.py next` always
returns the one directly executable next command (`do`), what is blocked
(`not_yet`), and the exit code it would give. No one memorizes the 26+
subcommands.

Manually, the flow is:

```bash
python3 bin/report.py init  --route planned --change <id> --repo <repo> --task-dir <td>
python3 bin/plan.py   scaffold --kind <site|tool|…> --task-dir <td>      # planned route
# … roles are dispatched through jiuwenswarm: proposal → specs → author → design → review …
python3 bin/plan.py   validate --change <id> --repo <repo>               # signed verdict
python3 bin/report.py deliver --task-dir <td> --repo <repo> --outcome completed
python3 bin/report.py gate   --request --task-dir <td>                   # human decides
python3 bin/plan.py   close  --change <id> --repo <repo> --task-dir <td> # merge + archive
```

Routing is measured, not guessed: 1–3 changed files go **inline**; 4 or more go
through the **planned** route (the threshold is one number in
`config/collapsed.config.yaml`, and `deliver` re-measures it against the real
diff — an inline route carrying too large a change stops the task for a person).

### 3. Every change starts as a PRD

A change begins as a PRD in `docs/` stating the measured problem, the root cause,
the requirement and — critically — the **reverse tests** that prove the fix. The
`CHANGELOG.md` entry for each version links back to its PRD and its measurements.

## Architecture

```
person (reads the diff, approves) ── MERGE_GATE ──┐
                                                 ▼
Claude Code (executor) ── bin/report.py   four states · G-DELIVER-1
  reads / writes / tests
  one worktree per task          (spec validity: openspec validate --strict,
      │                           run by report.py at delivery time)
      │
      └── role dispatches ── Jiuwenswarm gateway (systemd sandbox)
            one fresh session per role, event frames on disk
            planner · author · ui-designer · reviewers (1 axis, 1 persona each)
            validator · archiver · codegraph (Task-tool subagents)
                    │
                    └── Openjiuwen agent core
                          session runtime · model clients · memory/persistence
            every conclusion lands as a signed record; the caller only reads records
```

- **Collapsed execution runtime** — the coding agent is the executor; there is no
  orchestration middleware. The delegated-orchestrator generation was retired on
  evidence (rollback anchor `v0.5.1-delegated-final`), and the budget/oracle
  planes with it (anchors `v0.8.0`, `v0.9.0`).
- **Specialization through dispatch, not through a monolith** — each role is a
  Jiuwenswarm session with its own frames on disk and a boundary baseline; a role
  writing outside its artifact's path fails the dispatch. Infrastructure enforces
  the separation that prompts alone cannot.
- **Signed records over re-execution** — validation, graph, status, design and
  archive conclusions are written as signed records; anyone downstream verifies by
  reading, which makes the system auditable and cheap.
- **The human is a gate, not a bottleneck** — people read deliverables and approve
  merges; everything machine-checkable (spec strictness, landed diff, boundary,
  digest pins, contradictions) is checked by machines before the human ever looks.
- **Accepted cost, stated openly** — no machine judges artifact correctness and
  nothing caps a run's cost; both are visible only to a person who looks. That is
  the accepted price of building nothing upstream does not provide.

## Status

Runtime at v0.18.x (see `CHANGELOG.md` — every version entry carries its
measurements). Active lines: codegraph structure-first planning, phase-chain
automation, multi-target installs.
