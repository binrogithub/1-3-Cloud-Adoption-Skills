# LLMWiki platform — capabilities delivered by epic-impl-v1

## ADDED Requirements

### Requirement: Verified answers only
Every served answer SHALL come from the `llmwiki` role via a successful dispatch, and every
numeric, dated, URL, unit-bearing or configured-term claim SHALL be checked against a page
cited in the same sentence or table row before the answer is shown.

#### Scenario: unit mismatch fails closed
- **WHEN** an answer says "48.8 GB" and the cited page says "48.8 TB"
- **THEN** the claim is redacted in place and the ask is `partially_verified`

#### Scenario: unanswerable questions abstain
- **WHEN** the wiki has no evidence for the question in any of EN/ES/PT-BR
- **THEN** the answer is the NOT_IN_WIKI message and no model call is made when retrieval is empty

#### Scenario: role not dispatched means nothing is served
- **WHEN** the event stream carries no successful Agent tool result with agent_id `llmwiki` (e.g. agent mode)
- **THEN** the ask fails with `role_not_dispatched` and no answer text is returned

### Requirement: The wiki changes only through approved change sets
Pages SHALL be written by the glue when a human (or the explicitly configured policy actor)
approves a mechanically validated change set; compile output that fails validation
becomes `invalid` and never touches pages.

#### Scenario: fabricated fact in compile output is rejected
- **WHEN** a compiled page cites a value absent from its source snapshot
- **THEN** the change set is stored as `invalid` with the offending claim named

#### Scenario: file-back of a good answer
- **WHEN** a curator files a grounded ask
- **THEN** an `faq/` change set is created whose citations resolve to real L1 snapshots and awaits approval

### Requirement: Isolation of the dedicated instance
The dedicated JiuwenSwarm instance SHALL run stock binaries with its own data dir and ports,
its code-mode working folders SHALL land outside the repository, and deny-listed tools SHALL NOT
execute headless.

#### Scenario: shell tool is denied headless
- **WHEN** a headless prompt asks the main agent to run a shell command touching the filesystem
- **THEN** the tool result is a permission denial, no probe file appears, and no wiki write happens

### Requirement: Confidential sources are filtered before retrieval
Pages backed by confidential sources SHALL never enter the evidence pack for a reader or
contributor; the filter SHALL run between search and pack construction.

#### Scenario: reader ask over a confidential page
- **WHEN** the only matching page is confidential and the asker is a reader
- **THEN** the ask abstains and the hidden slug is reported, while a curator sees the page

### Requirement: Operable service
The platform SHALL expose a doctor command, a health endpoint carrying version and git SHA,
Prometheus metrics, nightly lint with a written `_meta/lint-report-<date>` page, and
backups whose restore MUST be tested.

#### Scenario: out-of-date process is detectable
- **WHEN** the health endpoint's git SHA differs from the deployed revision
- **THEN** the freshness gate (ag8) fails

#### Scenario: backup restores
- **WHEN** the nightly backup runs
- **THEN** its pg_dump loads into a throwaway database and the page, chunk and mirror counts agree
