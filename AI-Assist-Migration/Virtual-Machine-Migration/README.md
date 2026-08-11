# Virtual Machine Migration

This directory covers skills and tools for migrating virtual machines and server workloads to Huawei Cloud ECS.

## Scenarios

- [Vmware-Migration](./Vmware-Migration/) - VMware to Huawei Cloud migration using MGC/SMS with Terraform automation. Includes cross-region migration skill with runbook, lessons learned, and reusable bundles.
- [huaweicloud-sms-migration](./huaweicloud-sms-migration/) - Server Migration Service (SMS) skill for migrating on-premises or cloud VMs to Huawei Cloud ECS.

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
