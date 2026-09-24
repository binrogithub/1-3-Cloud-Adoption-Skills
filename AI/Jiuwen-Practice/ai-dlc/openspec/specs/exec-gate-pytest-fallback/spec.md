# exec-gate-pytest-fallback Specification

## Purpose
The execution gate measures the suite, not the ini file's plugin
wishlist.

## Requirements

### Requirement: a usage-error pytest probe retries with addopts cleared

When the pytest probe exits rc 4 (usage error), run_execution_gate
SHALL retry once with `-o addopts=` appended to the command, record
both attempts in output_tail and the fallback on the tool entry, and
take the retry's verdict as the gate's; a rc-1 probe (a failing suite)
and non-pytest tools SHALL NOT trigger the retry.

#### Scenario: nominal

- **WHEN the project's addopts name an uninstalled plugin and the
  cleared-addopts retry runs the suite green**
- **THEN the gate SHALL pass with the fallback recorded**

#### Scenario: the retry fails too

- **WHEN the cleared-addopts retry also fails**
- **THEN the gate SHALL fail with the retry's rc**
