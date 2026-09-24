---
name: autoops-ansible-operator
description: Access E02 pre-authorized service automation through the E01 Rundeck boundary.
version: 1
allowed_roles: [ansible-operator]
---

# AutoOps Ansible Operator

Route service automation through `#autoops-project-manager`. This role has no direct Ansible execution authority. It can only request a published service action through E01 after explicit confirmation.
