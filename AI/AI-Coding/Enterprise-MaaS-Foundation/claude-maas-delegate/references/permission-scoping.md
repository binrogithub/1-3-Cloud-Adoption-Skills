# Permission scoping for `DELEGATE_ALLOWED_TOOLS`

A practical reference for constructing a `DELEGATE_ALLOWED_TOOLS` value for a
delegated task. Every claim below is verified against the live harness, not
inferred from documentation.

## What actually works (tested)

- **Bare tool name**, e.g. `Bash` — grants the entire tool, every command, no
  restriction. This is what the `Implementation` preset
  (`Read,Write,Edit,Bash,Glob,Grep`) already does.
- **`Bash(<literal command prefix>:*)`** — e.g. `Bash(git add:*)`,
  `Bash(git commit:*)`, `Bash(python3.12 -m pytest:*)` — restricts to commands
  whose text starts with that exact literal prefix, with anything after the
  trailing `:*` accepted as arguments. Verified working for git subcommands and
  for a fixed test-runner invocation.
- **Exact literal full command** with no wildcard at all, e.g.
  `Bash(bash tests/collapse/ok_gate.sh)` — matches only that precise command.
  Verified working; useful when the exact command is known in advance and you
  want the narrowest possible grant.

```sh
DELEGATE_ALLOWED_TOOLS='Read,Write,Edit,Bash(python3.12 -m pytest:*),Bash(git add:*),Bash(git commit:*)'
```

## What does NOT work

- **A `*` glob in the middle of a pattern** to match a family of filenames, e.g.
  `Bash(bash tests/collapse/*.sh:*)` or `Bash(bash tests/collapse/:*)` — neither
  matches real filenames. The `*` is treated as a literal character in this
  position; only a trailing `:*` immediately after a fixed literal prefix acts
  as a wildcard. To allow running any of several known scripts, list each one as
  its own exact literal entry:

```sh
# Not a glob — each script must be enumerated:
DELEGATE_ALLOWED_TOOLS='Read,Bash(bash tests/collapse/ok_gate.sh),Bash(bash tests/collapse/plan_gate.sh)'
```

- **Never use a generic shell-escape-hatch prefix** such as `Bash(bash -c:*)` or
  `Bash(sh -c:*)`. Since arbitrary code can be wrapped inside the quotes of a
  `bash -c "..."` invocation, a pattern like this matches (and thus authorizes)
  literally anything, defeating the purpose of scoping. Verified: under
  `Bash(bash -c:*)`, a `bash -c "rm -rf <target>"` executed with zero additional
  prompt.

## The limitation that applies no matter which form you use

None of the forms above protect against command chaining. Once a command's
literal text starts with (or exactly matches) an allowed entry, the entire
command line executes as written, including anything appended with `&&`, `;`,
or a pipe. Verified against both a wildcarded prefix
(`Bash(python3.12 -m pytest:*)`) and an exact literal entry
(`Bash(bash tests/collapse/ok_gate.sh)`): appending `&& rm -rf <target>` after
either allowed command executed the `rm -rf` with no further approval prompt.

**Treat any `Bash` grant — bare, prefixed, or exact — as full shell trust for
that invocation.** It is a way to get past the headless "This command requires
approval" wall (see [PRD_ALLOWEDTOOLS_CHAINING_V1.md](PRD_ALLOWEDTOOLS_CHAINING_V1.md)
for why that wall exists and why `acceptEdits` alone does not clear it for
Bash), not a command-injection sandbox. Real safety still depends on
routing-policy scope and on the delegating agent independently checking the
task's `acceptance` command result afterward.

## Recommended pattern for a delegated task that needs to run tests and commit

Prefer giving a delegated sub-task Write/Edit only (no `Bash` at all) when the
task is pure content generation. When a task genuinely needs to run tests or
commit:

- Grant only the exact commands the task is known to need, generated fresh per
  task from the actual repo state — never a static broad list.

```sh
DELEGATE_ALLOWED_TOOLS='Read,Write,Edit,Bash(python3.12 -m pytest:*),Bash(git add:*),Bash(git commit:*)'
```

- If decomposing a larger piece of work into multiple concurrent Claude-MaaS
  sub-tasks (a fan-out pattern), give each sub-task Write/Edit only and no git
  access at all; have the orchestrator collect each sub-task's output and perform
  `git add`/`git commit` itself, once, after review. This avoids two independent
  problems at once: git's index lock has no automatic retry (a genuine concurrent
  `git commit` collision fails immediately —
  `fatal: Unable to create '.git/index.lock': File exists.`, exit 128 —
  verified), and it preserves independent verification of each sub-task's output
  before it's committed.
