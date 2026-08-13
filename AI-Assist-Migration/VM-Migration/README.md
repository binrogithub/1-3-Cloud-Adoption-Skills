# VM Migration

This directory covers skills and tools for migrating virtual machines from source clouds to Huawei Cloud ECS.

## Scenarios

- [huaweicloud-sms-migration](./huaweicloud-sms-migration/) - Server Migration Service (SMS) skill for migrating on-premises or cloud VMs to Huawei Cloud ECS.

> **Future scenarios:** AWS EC2 to Huawei ECS, Azure VM to Huawei ECS, GCP GCE to Huawei ECS, and other cloud-to-cloud VM migrations will be added under this category.

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
