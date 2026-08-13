# Datacenter On-Premise Migration

This directory covers skills and tools for migrating on-premises datacenter workloads to Huawei Cloud ECS.

## Scenarios

- [Vmware-Migration](./Vmware-Migration/) - VMware to Huawei Cloud migration using MGC/SMS with Terraform automation. Includes cross-region migration skill with runbook, lessons learned, and reusable bundles.

> **Future scenarios:** Physical server migration, Hyper-V migration, KVM migration, and other on-premises virtualization platforms will be added under this category.

## Format

Each scenario follows this structure:
```
Scenario/
|-- README.md                    # Scenario overview and instructions
+-- skill-name/
    |-- SKILL.md                 # Metadata + instructions
    |-- scripts/                 # Executable code
    |-- references/              # Documentation
    |-- assets/                  # Templates, resources
    +-- tools/                   # Helper utilities
```
