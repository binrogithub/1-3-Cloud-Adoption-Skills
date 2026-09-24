---
name: openspec-author
description: Authoring conduit — a dispatched role fetches its own artifact
  instructions by running the openspec CLI through this skill, rather than
  improvising from the prompt. Called by plan.py dispatch/phase for planned-
  route change artifacts (proposal/specs/design/tasks).
---

# openspec-author — artifact authoring conduit

## What you are

You are the role writing **one** openspec change artifact for a planned route
(proposal, specs, design, or tasks). The instructions for the artifact you
must write are **not** in your dispatch prompt — on purpose. Your prompt
carries the change id and the artifact name; the actual authoring guidance
comes from the openspec CLI, fetched through this skill.

## What to run

Run, with the `<artifact>` and `<change_id>` your dispatch prompt gave you:

```
openspec instructions <artifact> --change <change_id> --json
```

Read the JSON it returns. It carries the `instruction`, the `template`, and
the output path the artifact must be written to. Follow them exactly — write
the artifact to the path it reports, in the shape the template gives, guided
by the instruction. Do not invent a different output path, and do not pass
`--schema`; openspec auto-detects the schema from the repo's `config.yaml`.

## If it fails

If the CLI is unavailable, returns an error, or the artifact/change does not
resolve: do not improvise, do not guess a different artifact name, do not
retry with a different schema, and do not write anything from memory. Follow
the stop protocol your dispatch prompt already gives you — this file does not
repeat it. Stop and report exactly what happened.
