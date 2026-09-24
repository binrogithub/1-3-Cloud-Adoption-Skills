# JiuwenSwarm AutoOps

JiuwenSwarm AutoOps is an operations glue layer for the native JiuwenSwarm TUI. It accepts natural-language operations requests, lets ProjectManager select a specialist role, and invokes adapters for Loki, Prometheus, OpenSearch, Rundeck, Ansible, the Kubernetes API, Huawei Cloud CSS, or NOLI. This project does not modify or replace the source code of these open-source components.

## Supported operations scenarios

| Scenario | Role and flow | Current capability and boundary |
|---|---|---|
| Investigate local Linux or application logs | ProjectManager → **E05 Log Investigator** → Loki; falls back to the local systemd journal when Loki is unavailable | Read-only analysis with the time range, log evidence, and coverage gaps reported. The local account must be allowed to read the journal. |
| Review service metrics, error rates, or latency | ProjectManager → **E04 Metrics Observer** → Prometheus | Read-only queries for configured targets and metric profiles. No data is distinguished from a value of zero. |
| Correlate logs, metrics, and historical changes | ProjectManager / SwarmFlow → **E05 + E04**; may add **E06 Event Investigator** → OpenSearch when log evidence shows anomalies | Read-only parallel investigation. Missing sources remain visible; incomplete evidence is not presented as a confirmed root cause. |
| Inspect a host or run a registered operations runbook | ProjectManager → **E01 Runbook Operator** → fixed Rundeck Job | Only published Jobs are allowed. Write actions require an external authorization record bound to the task. |
| Ensure an allowlisted service is running | ProjectManager → **E02 Ansible Operator** → E01/Rundeck → fixed Ansible Job | Only the `ensure` action for `autoops-demo` is currently published. Arbitrary playbooks, host commands, and service names are not accepted. |
| Inspect a Kubernetes workload | ProjectManager → **E03 Kubernetes Operator** → Kubernetes API | Read-only inspection of registered clusters, namespaces, and workloads. Recovery or write actions require target-specific validation; this is not unrestricted kubectl access. |
| Monitor Huawei Cloud CSS capacity and plan scaling | ProjectManager → **css_auto** → CSS API/KooCLI | Reads registered CSS clusters and produces bounded scaling plans. Changes go through a fixed Runbook, policy, and human approval, and are limited to permitted data-node operations. |
| Investigate NOLI A10 and fixed-access events such as FTTH/PON, OLT/ONT, and BNG/PPPoE | ProjectManager → **NetOps** → NOLI adapter or fixed-access simulator | Read-only investigation. Synthetic data is clearly labeled. Real NOLI access requires endpoint and credentials; network changes are outside the current release scope. |
| Verify a registered recovery action | **Recovery Verifier** → independent read-only health probe | Uses only published service, Kubernetes, or CSS verification profiles. It does not perform repairs. |

**ProjectManager is the standard entry point for operations requests in the TUI.** Routine log queries are routed to E05. Parallel workflows are used when the user explicitly requests cross-source or multi-role investigation. Roles do not have unrestricted authority: write actions are constrained by fixed adapters, allowlists, pre-authorization, and verification boundaries.

### Role directory

| Role | Responsibility | Main components |
|---|---|---|
| **ProjectManager** (`project-manager`) | Understand the request and scope, route it to a specialist, and summarize the result | JiuwenSwarm and AutoOps project routes |
| **E01 Runbook Operator** (`runbook-operator`) | Run registered read-only checks or controlled Runbooks | Rundeck |
| **E02 Ansible Operator** (`ansible-operator`) | Request registered Ansible service actions | Ansible Core, invoked through Rundeck |
| **E03 Kubernetes Operator** (`kubernetes-operator`) | Inspect registered Kubernetes workloads | Kubernetes API / kubectl adapter |
| **E04 Metrics Observer** (`metrics-observer`) | Query metrics, trends, and health | Prometheus |
| **E05 Log Investigator** (`log-investigator`) | Investigate Loki or local journal logs | Loki and systemd journal |
| **E06 Event Investigator** (`event-investigator`) | Search historical changes and audit events | OpenSearch |
| **css_auto CSS Operations Specialist** (`css_auto`) | Monitor CSS traffic, data capacity, cluster health, and bounded scaling plans | Huawei Cloud CSS API or KooCLI |
| **NetOps** (`netops`) | Investigate NOLI A10 and fixed-access network events | NOLI API and fixed-access simulator |
| **Recovery Verifier** (`recovery-verifier`) | Independently verify completed actions using read-only checks | Registered business probes / APIs |
| **Ops Leader** (`ops-leader`) | Early integration-validation role for MaaS/TUI connectivity | JiuwenSwarm |

Alertmanager event intake and dispatch are handled by the AutoOps watcher integration. Grafana currently provides dashboards; neither component has a separately published Agent role callable by ProjectManager. E07 Alert Observer and E08 Dashboard Navigator are names from an earlier Epic plan, not implemented roles. Use ProjectManager for normal operations; Ops Leader is an early integration-validation role, not the primary router.

## Installation and configuration

Prerequisites: Linux, Python 3.9+, and an installed JiuwenSwarm backend/TUI that can be started. The AutoOps installer publishes this project's adapters, Skills, and configuration templates. It does not install or modify upstream JiuwenSwarm, Loki, Prometheus, OpenSearch, Rundeck, or Ansible.

```bash
cd AI/AI-Applications/jiuwenswarm-autoops
sudo ./scripts/install-autoops.sh --bin-dir /usr/local/bin --configure-model
```

The installer publishes the runtime to `/opt/Jiuwenswarm_AutoOps`, AutoOps configuration to `/etc/jiuwenswarm-autoops`, and task state to `/var/lib/jiuwenswarm-autoops`. The `--configure-model` wizard prompts for the MaaS endpoint, model, and API key (the key is entered without echo) and updates the current JiuwenSwarm user's standard `~/.jiuwenswarm/config/.env`. That file may contain other JiuwenSwarm settings; the wizard updates only the four model fields, preserves the rest, and saves the file with mode `0600`.

The single model entry uses JiuwenSwarm's native dotenv fields: `API_BASE`, `API_KEY`, `MODEL_NAME`, and `MODEL_PROVIDER`. The recommended defaults are Huawei Cloud MaaS's OpenAI-compatible endpoint and `deepseek-v4.1-flash`; confirm that the model is available to your MaaS account. No real API key is included in this repository. To change the model later, use `sudo /opt/Jiuwenswarm_AutoOps/scripts/configure-model.py`. The wizard targets the user who invoked the installer, so model settings do not need to be duplicated across role files, installation scripts, or environment-variable files.

To skip interactive configuration, run the installer first, then run the secure configuration wizard separately. The template is available at `config/model.env.example`. Do not overwrite an existing JiuwenSwarm `.env` with the template because it may contain other upstream settings.

```bash
sudo ./scripts/install-autoops.sh
sudo /opt/Jiuwenswarm_AutoOps/scripts/configure-model.py
```

Configure data sources, CSS profiles, NOLI, and Rundeck credentials using the corresponding `/etc/jiuwenswarm-autoops/*.env.example` files or configuration directories. The installer preserves existing customer configuration by default. To download the external components listed by the project, explicitly pass `--install-components`. MaaS connectivity checks and the chat launcher read the model settings from the same JiuwenSwarm user `.env`. See the [installation guide](docs/autoops-install.md) and [release operations manual](docs/release-operations.md) for details.

## Start the TUI

Make sure the JiuwenSwarm backend is running, then start the AutoOps TUI entry point:

```bash
Jiuwen_autoops_tui
```

Example request:

```text
Investigate error logs from the local Linux host for the last 24 hours and report log coverage.
```

To specify a service and time range:

```text
Analyze errors for chatbot-ui from the last 30 minutes; service=chatbot-ui; since-minutes=30
```

ProjectManager returns a task identifier, the selected role, evidence, and coverage status. See the [ProjectManager Skill](skills/autoops-project-manager/SKILL.md) for routing behavior and the [role configuration](config/roles/) for the published role boundaries.

## Optional open-source component downloads

In a development environment, `download.sh` downloads pinned component artifacts to `/opt/JiuwenSwarm`. This only stages files; it does not mean the components are installed, running, or connected to AutoOps.

```bash
./download.sh
```

See the [component download record](docs/download-components.md) for the component list and checksum details.

## Product and release documentation

- [Release environment support matrix](docs/release-environment.md)
- [Release notes](docs/release-notes.md)
- [Installation guide](docs/autoops-install.md)
- [Release operations manual](docs/release-operations.md)
- [MaaS and TUI configuration](docs/e00-maas-tui-runbook.md)
- [Component download record](docs/download-components.md)
- [CSS operations validation](docs/css-stability-release-decision.md)
