# materialize-via-dispatch Specification

## Purpose
Every byte of OpenDesign material that reaches a delivery passed
through a jiuwenswarm session the plane can prove.

## Requirements

### Requirement: materialization is a gateway dispatch

design-materialize SHALL copy template material via a jiuwenswarm
session running the normalized copy command; the plane SHALL verify
the frames carry that command with rc 0, cross-check the command's
JSON report against the files standing under dest, and sign the
manifest with the session name and dispatched=true. A refused session,
a missing normalized call, or a report that disagrees with the
standing files SHALL exit inconclusive without a manifest.

#### Scenario: nominal

- **WHEN the session runs the normalized copy successfully**
- **THEN the manifest SHALL carry session + dispatched=true and the
  standing files' kinds/counts/shas**

#### Scenario: lying report

- **WHEN the session's report names files that do not stand**
- **THEN materialization SHALL be refused inconclusive**

### Requirement: the offline path exists only behind the kill-switch

With AI_DLC_NO_MATERIALIZE_DISPATCH=1 the copy SHALL run locally
with dispatched=false and no session; without the flag no local copy
path SHALL exist.

#### Scenario: nominal

- **WHEN the kill-switch is set**
- **THEN materialization succeeds without opening any session**
