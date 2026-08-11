# CodeArts Overview

Design, create, and operate Huawei Cloud CodeArts projects and DevOps pipelines using hcloud CLI (KooCLI). This scenario covers two complementary skills: project design (creating and configuring CodeArts Req projects) and DevOps operations (Repo, Check, Build, Artifact, TestPlan, Deploy, and Pipeline management).

---

## Overview

```
Design Phase                           Operations Phase
+-----------------------+              +-----------------------+
|  CodeArts Req         |              |  CodeArts Repo        |
|  (ProjectMan)         |              |  Check / Build        |
|  - Create project     |    --->      |  Artifact / TestPlan  |
|  - Configure members  |              |  Deploy / Pipeline    |
|  - Set description    |              |  - CI/CD operations   |
+-----------------------+              +-----------------------+
```

The scenario is divided into two phases:
1. **Project Design** — Create and configure a CodeArts Req project (Scrum, Kanban, Normal, or Phoenix type) with members and roles
2. **DevOps Operations** — Operate the full CI/CD pipeline: code repository, checks, builds, artifacts, test plans, deployments, and pipeline orchestration

---

## Skills Used

| Skill | Role | When |
|-------|------|------|
| [huawei-codearts-project-design](./huawei-codearts-project-design/SKILL.md) | Design and create CodeArts Req projects | Phase 1: Project setup |
| [huawei-codearts-devops-operations](./huawei-codearts-devops-operations/SKILL.md) | Operate CodeArts Repo, Build, Check, Deploy, Pipeline | Phase 2: CI/CD operations |

---

## Prerequisites

| Tool | Purpose | How to verify |
|------|---------|---------------|
| OpenCode | AI agent with MCP support | `opencode --version` |
| Huawei Cloud MCP | Call Huawei Cloud APIs | Configured in opencode |
| hcloud CLI (KooCLI) | Direct API calls | `hcloud --version` |

### What you need

- **Huawei Cloud account** with CodeArts enabled
- **AK/SK** with permissions for CodeArts (ProjectMan, Repo, Check, Build, Artifact, TestPlan, Deploy, Pipeline)
- **Region** where CodeArts is available (e.g. `cn-north-4`, `la-north-2`)

---

## Workflow

### Phase 1: Project Design

1. Discover existing projects (`ProjectMan ListProjectsV4`)
2. Validate project name (uniqueness, naming rules)
3. Create or reuse project (`ProjectMan CreateProjectV4`)
4. Configure description and members

### Phase 2: DevOps Operations

1. Manage code repository (`Repo`)
2. Run code checks (`Check`)
3. Execute builds (`Build`)
4. Manage build artifacts (`Artifact`)
5. Create and run test plans (`TestPlan`)
6. Deploy applications (`Deploy`)
7. Orchestrate full pipeline (`Pipeline`)

---

## Internal Documentation

| Document | Skill | Description |
|----------|-------|-------------|
| [Designing_and_Creating_CodeArts_Projects_with_KooCLI.docx](./huawei-codearts-project-design/assets/Designing_and_Creating_CodeArts_Projects_with_KooCLI.docx) | project-design | Word guide for project creation |
| [Using_CodeArts_Repo_Check_Build_Artifact_TestPlan_Deploy_Pipeline_with_KooCLI.docx](./huawei-codearts-devops-operations/assets/Using_CodeArts_Repo_Check_Build_Artifact_TestPlan_Deploy_Pipeline_with_KooCLI.docx) | devops-operations | Word guide for CI/CD operations |
