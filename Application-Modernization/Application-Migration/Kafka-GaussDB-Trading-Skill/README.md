# Kafka GaussDB Trading Skill

This child skill package focuses on migrating or designing high-frequency transaction applications on Huawei Cloud with DMS for Kafka as the event backbone and GaussDB as the transactional state store. It is intended for application migration scenarios where reliability, idempotent processing, partitioning, retry handling, and operational deployment patterns must be preserved.

## Included Assets

- [SKILL.md](./SKILL.md): Main skill definition, default architecture, and delivery guidance
- [assets/](./assets): Bundled Java demo assets for a runnable reference implementation
- [references/](./references): Architecture, deployment, Java demo, and performance guidance
- [scripts/](./scripts): Helper scripts for smoke checks, property rendering, and topic planning

## Typical Use

- Design or migrate a Kafka plus database transaction workflow to Huawei Cloud
- Build a Java-based demo using DMS for Kafka and GaussDB
- Define partitioning, idempotency, inbox and outbox, and DLQ patterns
- Validate connectivity, deployment topology, and throughput-oriented defaults
