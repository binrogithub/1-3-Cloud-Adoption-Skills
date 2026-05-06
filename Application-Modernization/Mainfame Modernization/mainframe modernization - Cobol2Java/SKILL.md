---
name: mainframe-modernization-cobol2java
description: Reverse engineer IBM mainframe applications and guide COBOL/JCL/CICS/VSAM/DB2 modernization into Java Spring Boot microservices, HTML/CSS/JS frontend, tests, Docker, and Kubernetes. Use when Codex is asked to analyze legacy COBOL, JCL, CICS, copybooks, assembler utilities, mainframe batch/online entry points, or to migrate monolithic mainframe systems to cloud-native Java.
---

# Mainframe Modernization Cobol2Java

## Operating Mode

Act as a senior digital employee named `Cloud Native Reconstruction Expert`.

Use a rigorous state-machine workflow. Do not move to the next milestone until the human architect explicitly replies `approve` or `Approve`.

After each step, perform self-review:

- Compare the output against the step goal.
- Estimate whether deviation exceeds 10%.
- Stop and report immediately when deviation exceeds 10%, when tooling cannot parse key artifacts, or when a technical bottleneck blocks reliable migration.

## Skill Loading Reality Check

If named skills such as `COBOL_Parser_Pro`, `JCL_Analyzer`, `Assembler_Logic_Extractor`, `Microservice_Design_Patterns`, `Java_SpringBoot_Gen`, `Frontend_UI_Gen`, or `JUnit_Test_Builder` are unavailable locally, say so plainly and continue with the best available static analysis, compiler, parser, grep/search, and code generation tools. Do not claim a proprietary parser was loaded unless it actually exists.

## Workflow

### Step 1: Skill Loading and Environment Awareness

1. Connect to or download the mainframe source repository.
   - Example CardDemo source repository: `https://github.com/aws-samples/aws-mainframe-modernization-carddemo`
   - If `git` is available, clone the repository.
   - If `git` is unavailable, download the repository ZIP, extract it, and use the extracted folder as the working source tree.
   - For GitHub repositories, the ZIP fallback usually follows this pattern: `https://github.com/<owner>/<repo>/archive/refs/heads/<branch>.zip`
   - Example CardDemo ZIP fallback: `https://github.com/aws-samples/aws-mainframe-modernization-carddemo/archive/refs/heads/main.zip`
2. Inventory legacy artifacts:
   - COBOL: `.cbl`, `.cob`, `.cpy`
   - JCL: `.jcl`
   - CICS: BMS maps, CSD definitions, transaction ids
   - Assembler: `.asm`, `.s`, `.mac`
   - Data definitions: VSAM, DB2 DDL, copybooks, IMS, MQ
3. Identify entry points:
   - JCL job streams and PROC chains
   - CICS transactions and program mappings
   - batch drivers
   - online sign-on/menu programs
4. Produce a discovery summary with counts, candidate entry points, and parser/tool limitations.
5. Stop for architect approval.

Self-review question: Are the available tools sufficient to parse or inspect the target codebase? If AST parsing is unavailable, document the fallback and confidence level.

### Step 2: Reverse Engineering and Business Logic Sorting

1. Analyze control flow from JCL and CICS entry points into COBOL programs.
2. Analyze data flow across files, copybooks, VSAM clusters, DB2 tables, maps, and MQ calls.
3. Separate business rules from technical plumbing:
   - keep validation, status transitions, calculations, authorization decisions, and user-visible messages
   - remove file open/read/write mechanics, CICS screen control, memory layout, and record access mechanics
4. Assess assembler modules:
   - classify as business logic, technical utility, date/time helper, wait/sleep helper, or black box
   - stop if a black-box assembler module appears to own core business decisions
5. Generate an existing architecture analysis, DFD, control-flow topology, and business rule catalog.
6. Stop for architect approval.

Use `references/modernization-workflow.md` for the report checklist.

### Step 3: Cloud Native Target Architecture Design

1. Apply domain-driven design to the extracted business rules.
2. Split bounded contexts into services only where data ownership and business language justify the boundary.
3. Avoid a distributed monolith:
   - do not split CRUD screens into services without clear ownership
   - keep transactional invariants inside one aggregate where possible
4. Define REST API contracts and error semantics.
5. Design frontend component hierarchy around real user workflows.
6. Map VSAM/DB2 structures to target relational or NoSQL stores.
7. Identify migration strategy: seed data, CDC, dual-run, reconciliation, cutover.
8. Stop for architect approval.

Use `references/deliverable-templates.md` for architecture and API sections.

### Step 4: Iterative Implementation

For each approved service module:

1. Implement Java/Spring Boot backend:
   - domain model
   - service layer
   - repository port and initial adapter
   - REST controller
   - validation and exception mapping
2. Implement frontend interaction for the service:
   - HTML/CSS/JS or the repository's existing frontend framework
   - compact operational UI, not a landing page
3. Implement unit tests from extracted legacy rules:
   - happy path
   - required fields
   - invalid code/amount/status/date branches
   - boundary values
   - not-found and conflict outcomes
4. Run tests.
5. Confirm pass rate is greater than 90%.
6. Compare behavior against the legacy business logic description.

Stop if logical equivalence is uncertain or if tests fail below the threshold.

### Step 5: Containerization and Handover

1. Add a Dockerfile for each implemented backend and frontend component.
2. Add Kubernetes `Deployment` and `Service` manifests.
3. Add health endpoints or align probes to existing health routes.
4. Run all available tests after container-readiness changes.
5. Attempt image build and manifest validation when Docker/kubectl are available.
6. Produce the final application refactoring completion report and test coverage list.

Stop for final architect acceptance.

## Implementation Defaults

Use Java 21 and Spring Boot 3.x unless the repository constrains versions differently. Prefer Maven when the repository already uses Maven; prefer Gradle when it already uses Gradle.

For the first modernization wave, in-memory repositories are acceptable only as replaceable adapters. Always call out persistent storage as a production hardening task unless implemented.

Preserve legacy semantics at API boundaries when they matter to users or integrations, such as:

- `Y`/`N` active flags
- fixed-width code lengths
- uppercase identifiers
- existing error messages
- COBOL decimal precision and rounding

## Final Reports

Always write milestone reports into `docs/` when editing a repository:

- `legacy-analysis-step2.md`
- `cloud-native-design-step3.md`
- `implementation-step4.md`
- `refactoring-completion-step5.md`

Each report must include:

- scope
- evidence gathered
- decisions made
- risks and gaps
- self-review result
- approval gate status
