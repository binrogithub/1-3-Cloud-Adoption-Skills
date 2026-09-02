# Team mode — the record

What was measured and read about running a review round through a
openjiuwen team, recorded where a reader proposing it will find it, so
the question is not reopened from the same starting point and
re-answered by the same experiments. Every point below carries the
evidence that settled it. Nothing here modifies openjiuwen source —
the code is cited read-only, in the reference checkout at
`<workspace-root>/reference/jiuwenswarm`.

## The findings

**1. A team is structurally a leader with teammates — there is no peer
model.** The runtime accepts exactly those two roles and silently
demotes anything else: `runtime_role()` returns the configured role
only when it is `leader` or `teammate`, and `leader` otherwise
(`jiwuenswarm/agents/harness/team/distributed_runtime.py:31-35`). The
loader completes the pair from the configuration's shape: when the
`agents` config names no leader one is built
(`jiwuenswarm/agents/harness/team/config_loader.py:377-385`), and when
it contains only a leader a teammate is added
(`config_loader.py:386-390`). Whatever is configured, what starts is a
leader plus teammates. The equal-reviewer round of `plan.py review` is
the peer model the runtime does not offer: three sessions, no leader,
each holding one axis.

**2. A configured roster for the wildcard team is not read on the
command-line path.** `modes.team.jiuwen_team.predefined_members` is
read by the Web
channel handler (`jiwuenswarm/gateway/channel_manager/web/app_web_handlers.py`)
and by the team assembly; no module under `jiwuenswarm/cli/` reads it.
Measured, not inferred: three adversarial personas (a security, a
performance and an operability reviewer) were written into
`~/.jiuwenswarm/config/config.yaml` under `modes.team.jiuwen_team.predefined_members`,
the gateway was restarted, and a team round ran for 2,672 frames. The
roster names appeared nowhere in the run; the leader named its own
workers from its own decomposition — `review-security-0`,
`review-performance-1`, `review-operability-2`. A team round cannot be
given named reviewers; the per-role dispatch already is.

**3. Duration, measured.** A completed team round: ~1,500 s wall
(workflow completed 4/4, an 8,692-character answer, ≈11 minutes). The
equal-reviewer round beside it: 174.3 s wall for three reviewers
dispatched concurrently (471.2 role-seconds across them — the wall is
shorter than the sum because they run together). An order of magnitude
apart, measured on the same round shape.

**4. The leader is not idle when it appears to be.** In the run's
reasoning the leader decides, starts its workflow, then blocks awaiting
a completion notification ("Let me wait for the notification") — the
slowness is structural waiting, not a defect, and the progress
invisibility follows from it: nothing is observable until the
notification arrives. The swarmflow tool it starts is leader-facing by
its own description, as read in the run — a teammate has no such tool,
so the workflow shape itself belongs to the leader.

## What this record means for proposals

`plan.py review --mode team` refuses by reference to this record, with
the three reasons already carried in the refusal: the named reviewers
cannot be given to a wildcard-matched team, its progress is invisible
until it ends, and it takes an order of magnitude longer than the
per-role dispatch in use. Refusing requires **no new experiment** —
unless the proposal names a fact this record does not cover, in which
case that fact, not the settled ones, is what the experiment measures.

## The inert roster, removed

The three personas of finding 2 sat in
`~/.jiuwenswarm/config/config.yaml` under `modes.team.jiuwen_team.predefined_members`
after the experiment, looking effective while no path this project
uses read them. Removed on 2026-08-31. The backup taken before they
were added is `~/.jiuwenswarm/config/config.yaml.bak.roster.1788130706`;
restoring the roster is a copy back, and it would change nothing on the
command-line path.
