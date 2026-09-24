# runtime-authorization Specification

## Purpose
Record the runtime settings the planning plane needs to run unattended, and the
failure modes measured on this host when they are absent.

## Requirements

### Requirement: The planning plane runs fully authorised across every permission layer

Tool permission prompts SHALL NOT gate the plane, because no responder exists in
a headless run. Three layers were measured and all three SHALL be satisfied.

#### Scenario: Configuring the layers

- **WHEN** the plane is prepared
- **THEN** the tool permission defaults SHALL grant execution
- **AND** the per-tool baselines SHALL grant execution, because a per-tool
  baseline overrides the default
- **AND** the settings SHALL live in our runtime configuration, never in
  dependency source
- **AND** the previous configuration SHALL be retained as a restorable backup

#### Scenario: A compound command trips the shell structure guard

- **WHEN** a role issues a command joining several subcommands
- **THEN** the parameter-level shell guard MAY interrupt it even though the tool
  baseline grants execution
- **AND** role prompts SHALL therefore instruct single simple commands
- **AND** the working directory SHALL be supplied by the dispatch rather than by
  a directory change inside the command

#### Scenario: An interrupt still appears

- **WHEN** an interrupt frame appears and no responder exists
- **THEN** the dispatch SHALL exit non-zero naming the tool and the argument
- **AND** it SHALL NOT return a successful envelope carrying a degenerate answer

### Requirement: The planning plane can reach the repository

The service sandbox SHALL be configured so the plane reads and writes the
repository it was pointed at.

#### Scenario: Granting reach

- **WHEN** the gateway is prepared for a repository tree
- **THEN** that tree SHALL be among the writable paths of the service unit
- **AND** the unit SHALL be reloaded and the service restarted before use
- **AND** the previous unit SHALL be retained as a restorable backup

#### Scenario: A private temporary namespace hides the target

- **WHEN** the service runs with a private temporary namespace
- **THEN** a repository under a temporary path SHALL NOT be used as a target,
  because the plane sees a different directory of the same name
- **AND** the target SHALL be a path the service shares with the caller

#### Scenario: Reach is missing

- **WHEN** the plane cannot read the repository or write its artifact
- **THEN** the task SHALL stop before planning begins
- **AND** the human SHALL be told which setting is absent

### Requirement: Gateway bookkeeping directories are excluded from the product surface

The gateway writes bookkeeping directories into the working tree. These SHALL be
excluded so the boundary check does not misreport.

#### Scenario: Evaluating the boundary

- **WHEN** the product surface diff is computed at the end of planning
- **THEN** the gateway file-operation history, the coding memory store and the
  prompt attachment directory SHALL be excluded
- **AND** any remaining path outside the change directory SHALL abort the task

#### Scenario: Only excluded directories were written

- **WHEN** the only paths outside the change directory are those bookkeeping
  directories
- **THEN** the boundary check SHALL pass
