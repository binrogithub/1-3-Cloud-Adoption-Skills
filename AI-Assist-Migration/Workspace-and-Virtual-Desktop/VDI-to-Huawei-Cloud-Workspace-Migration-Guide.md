# VDI to Huawei Cloud Workspace Migration Guide
## Re-Deploy Strategy Using Hermes Agent Skills

> **Strategy:** Re-deploy (rebuild from scratch on the target, then migrate user data) — as opposed to lift-and-shift disk imaging. This gives a clean, vendor-supported baseline on Huawei Cloud Workspace while preserving all user applications and data.

---

## Table of Contents

1. [Migration Overview](#1-migration-overview)
2. [Prerequisites & Tooling](#2-prerequisites--tooling)
3. [Phase 1 — Source VDI Assessment](#phase-1--source-vdi-assessment)
4. [Phase 2 — MSI Installer Discovery & Backup](#phase-2--msi-installer-discovery--backup)
5. [Phase 3 — Software Packaging & Staging](#phase-3--software-packaging--staging)
6. [Phase 4 — Target Environment Preparation](#phase-4--target-environment-preparation)
7. [Phase 5 — Software Deployment](#phase-5--software-deployment)
8. [Phase 6 — User Data Migration](#phase-6--user-data-migration)
9. [Phase 7 — Post-Deployment Verification](#phase-7--post-deployment-verification)
10. [Phase 8 — Cutover & Sign-Off](#phase-8--cutover--sign-off)
11. [Skill & Script Reference](#skill--script-reference)
12. [Troubleshooting](#troubleshooting)
13. [Checklist](#checklist)

---

## 1. Migration Overview

### What is the Re-Deploy Strategy?

Instead of copying a VDI disk image to the cloud (lift-and-shift), the re-deploy strategy:

1. **Inventories** all software on the source VDI
2. **Backs up** all MSI installers and downloads non-MSI installers
3. **Builds a clean** Huawei Cloud workspace desktop from a golden image
4. **Re-installs** all required software silently via `msiexec`
5. **Migrates user data** (profiles, files, settings)
6. **Validates** parity between source and target

### Why Re-Deploy?

| Factor | Lift-and-Shift | Re-Deploy |
|--------|---------------|-----------|
| Clean OS baseline | No - carries over VDI bloat | Yes - fresh vendor image |
| Driver compatibility | No - VDI drivers on cloud hypervisor | Yes - correct Huawei drivers |
| Licensing compliance | Hard to audit | Yes - explicit install log |
| Rollback | Difficult | Easy - rebuild target |
| MSI cache available | N/A | Yes - full installer backup |
| Time | Faster (disk copy) | Slower (reinstall) but cleaner |

---

## 2. Prerequisites & Tooling

### Hermes Agent Skills Used

| Skill | Category | Purpose | Phase |
|-------|----------|---------|-------|
| `windows-software-inventory` | software-development | Scan all installed software via registry | Phase 1 |
| `windows-msi-inventory` | software-development | Find, read, and back up cached MSI installers | Phase 2 |
| `msi-batch-installer` | software-development | Silently install MSI packages in bulk | Phase 5 |

### Environment Requirements

| Component | Requirement |
|-----------|-------------|
| **Source VDI** | Windows 10/11, PowerShell 3.0+, Python 3.11+, admin access |
| **Target** | Huawei Cloud Workspace desktop (Windows) |
| **Staging share** | SMB file share accessible from both source and target |
| **Hermes Agent** | Running on a management machine with access to both |
| **Huawei Cloud** | Workspace desktop pool configured, AD integration ready |

### Loading the Skills

Before starting, ensure all three skills are loaded in Hermes:

```
skill_view(name='windows-software-inventory')
skill_view(name='windows-msi-inventory')
skill_view(name='msi-batch-installer')
```

---

## Phase 1 — Source VDI Assessment

> **Goal:** Produce a complete inventory of all installed software on the source VDI.
> **Skill:** `windows-software-inventory`
> **Script:** `scan_software.py`

### Step 1.1: Run the Full Inventory Scan

On the **source VDI**, open a terminal and run:

```bash
python scan_software.py --full --json source_inventory.json --csv source_inventory.csv
```

### Step 1.2: Review and Classify the Inventory

Open `source_inventory.csv` in Excel or review the JSON. Classify each application:

| Category | Action | Examples |
|----------|--------|----------|
| **MSI-installed** | Back up MSI -> re-install on target (Phase 2-5) | 7-Zip, Inkscape, Blender, Notepad++ |
| **EXE-installed** | Download fresh installer from vendor | Chrome, Firefox, custom apps |
| **Store/UWP** | Re-install from Microsoft Store | Calculator, Photos, vendor Store apps |
| **System/Driver** | Skip - provided by golden image | GPU drivers, .NET Framework, VC++ Redist |
| **Deprecated** | Skip - no longer needed | Old tools, legacy runtimes |
| **License-required** | Verify license transfer | MS Office, Adobe, IDEs |

### Step 1.3: Search for Specific Software

```bash
python scan_software.py --search "Python"
python scan_software.py --search "Office"
python scan_software.py --search "Adobe"
```

> **Deliverable:** `source_inventory.json` + `source_inventory.csv` — complete software manifest of the source VDI.

---

## Phase 2 — MSI Installer Discovery & Backup

> **Goal:** Locate all cached MSI installers on the source VDI, read their properties, and back them up.
> **Skill:** `windows-msi-inventory`
> **Script:** `scan_msi_installers.py`

### Step 2.1: Discover All MSI Installers

```bash
python scan_msi_installers.py --props --json msi_inventory.json --csv msi_inventory.csv
```

### Step 2.2: Back Up MSI Installers

```bash
python scan_msi_installers.py --backup "\\\\staging-server\\migration\\msi-backup\\" --props
```

### Step 2.3: Check InstallSource for Original Named MSIs

```bash
python scan_msi_installers.py --props --json msi_with_source.json
```

> **Deliverable:** `msi-backup/` folder on staging share with all third-party MSI files + `msi_inventory.csv` manifest.

---

## Phase 3 — Software Packaging & Staging

> **Goal:** Organize all installers into a structured staging directory ready for deployment.

### Step 3.1: Create the Staging Structure

```
\\staging-server\migration\
├── msi-backup\              <- From Phase 2
├── exe-installers\          <- Downloaded EXE installers
├── configs\                 <- Application configuration files
├── user-data\               <- User profiles, files, settings
├── scripts\                 <- Deployment scripts
├── install.yaml             <- Deployment manifest
└── source_inventory.csv     <- From Phase 1
```

### Step 3.2: Create the Deployment Manifest

Create `install.yaml` to define the installation order and properties.

> **Deliverable:** Staging share with all installers, configs, scripts, and deployment manifest ready.

---

## Phase 4 — Target Environment Preparation

> **Goal:** Provision a clean Huawei Cloud Workspace desktop ready for software installation.

### Step 4.1: Provision the Target Desktop

In Huawei Cloud Workspace:
1. Select a golden image with latest Windows updates, Huawei agent, AD join
2. Provision a desktop for the target user
3. Verify network connectivity to staging share and AD

### Step 4.2: Verify Prerequisites on Target

```powershell
# Check admin rights
([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
# Check PowerShell version
$PSVersionTable.PSVersion
# Check Python
python --version
# Check network access
Test-Path "\\staging-server\migration\msi-backup\"
```

### Step 4.3: Copy Deployment Scripts to Target

```powershell
Copy-Item "\\staging-server\migration\scripts\*" "C:\Temp\msi-deploy\" -Recurse
```

> **Deliverable:** Clean Huawei Cloud Workspace desktop with network access to staging share and deployment scripts in place.

---

## Phase 5 — Software Deployment

> **Goal:** Silently install all MSI packages on the target desktop.
> **Skill:** `msi-batch-installer`
> **Scripts:** `install-msi.ps1` or `install-msi.cmd`

### Step 5.1: Deploy MSI Packages (PowerShell - Recommended)

```powershell
cd C:\Temp\msi-deploy
.\install-msi.ps1 -Path "\\staging-server\migration\msi-backup\" -UiMode silent -ContinueOnError:$true
```

### Step 5.2: Deploy MSI Packages (CMD - Alternative)

```cmd
cd /d C:\Temp\msi-deploy
install-msi.cmd "\\staging-server\migration\msi-backup\"
```

### Step 5.3: Install in Ordered Phases

```powershell
# Phase A: Runtimes
.\install-msi.ps1 -Path "\\staging-server\migration\msi-backup\runtimes\" -ContinueOnError:$false
# Phase B: Core applications
.\install-msi.ps1 -Path "\\staging-server\migration\msi-backup\core-apps\"
# Phase C: Specialized
.\install-msi.ps1 -Path "\\staging-server\migration\msi-backup\specialized\"
```

### Step 5.4: Review Installation Logs

Check `%TEMP%\msi-install-logs\` for failures. Search for `Return value 3`.

> **Deliverable:** All software installed on the target desktop. Installation summary report with pass/fail counts.

---

## Phase 6 — User Data Migration

> **Goal:** Transfer user profiles, documents, and settings from source VDI to target desktop.

### Step 6.1: Export User Data from Source

```powershell
$staging = "\\staging-server\migration\user-data\"
$user = $env:USERPROFILE
robocopy "$user\Documents" "$staging\Documents" /E /COPYALL /R:3 /W:5
robocopy "$user\Desktop" "$staging\Desktop" /E /COPYALL /R:3 /W:5
reg export "HKCU\Software" "$staging\user-reg-settings.reg" /y
```

### Step 6.2: Import User Data to Target

```powershell
$staging = "\\staging-server\migration\user-data\"
$user = $env:USERPROFILE
robocopy "$staging\Documents" "$user\Documents" /E /COPYALL /R:3 /W:5
robocopy "$staging\Desktop" "$user\Desktop" /E /COPYALL /R:3 /W:5
```

> **Deliverable:** User documents, desktop files, and application settings transferred to the target desktop.

---

## Phase 7 — Post-Deployment Verification

> **Goal:** Verify that the target desktop has the same software as the source VDI.
> **Skill:** `windows-software-inventory`

### Step 7.1: Run Inventory on Target

```bash
python scan_software.py --full --json target_inventory.json --csv target_inventory.csv
```

### Step 7.2: Compare Source vs. Target

```python
import json
with open('source_inventory.json') as f:
    source = json.load(f)
with open('target_inventory.json') as f:
    target = json.load(f)
source_names = {app['DisplayName'].lower() for app in source['registry']}
target_names = {app['DisplayName'].lower() for app in target['registry']}
missing = source_names - target_names
extra = target_names - source_names
print(f"MISSING on target ({len(missing)}):")
for app in sorted(missing): print(f"  X {app}")
```

> **Deliverable:** Verification report showing parity (or gaps) between source and target.

---

## Phase 8 — Cutover & Sign-Off

### Step 8.1: User Acceptance Testing (UAT)

Have the end user verify:
- [ ] All daily-use applications open and function correctly
- [ ] Documents and files are accessible
- [ ] Network resources accessible
- [ ] Performance is acceptable

### Step 8.2: Decommission Source VDI

After UAT sign-off:
1. Keep source VDI powered off for a grace period (7-14 days)
2. Archive inventory and installation logs
3. Decommission after grace period

---

## Skill & Script Reference

### Quick Reference: Which Skill for Which Phase

```
Phase 1 (Inventory)     ->  windows-software-inventory  ->  scan_software.py --full
Phase 2 (MSI backup)    ->  windows-msi-inventory       ->  scan_msi_installers.py --backup
Phase 5 (Deployment)    ->  msi-batch-installer         ->  install-msi.ps1 -Path <dir>
Phase 7 (Verification)  ->  windows-software-inventory  ->  scan_software.py --full (compare)
```

---

## Troubleshooting

### Phase 1: Inventory

| Issue | Cause | Fix |
|-------|-------|-----|
| Missing 32-bit apps | Didn't scan WOW6432Node | Use `--full` flag |
| `Win32_Product` hangs | Using WMI instead of registry | Use `scan_software.py` |

### Phase 2: MSI Backup

| Issue | Cause | Fix |
|-------|-------|-----|
| "Access denied" on MSI | C:\Windows\Installer is protected | Run as Administrator |
| Missing MSI file | Cache was cleaned | Download fresh from vendor |

### Phase 5: Deployment

| Issue | Cause | Fix |
|-------|-------|-----|
| Error 1603 | Not running as Admin | Use `run-elevated.ps1` |
| Error 1618 | Another MSI install running | Wait, scripts install sequentially |
| Error 1638 | Different version installed | Uninstall existing version first |
| Error 3010 | Success but reboot needed | Reboot and continue |

---

## Checklist

### Pre-Migration
- [ ] Hermes Agent running with all 3 skills loaded
- [ ] Source VDI accessible with admin credentials
- [ ] Staging share created and accessible
- [ ] Huawei Cloud Workspace desktop provisioned
- [ ] Network connectivity verified

### Phase 1 - Assessment
- [ ] `scan_software.py --full` run on source VDI
- [ ] Inventory reviewed and classified
- [ ] Stakeholders approved software list

### Phase 2 - MSI Backup
- [ ] `scan_msi_installers.py --props` run on source VDI
- [ ] MSI files backed up to staging share
- [ ] InstallSource directories checked for original named MSIs

### Phase 3 - Packaging
- [ ] Staging directory structure created
- [ ] `install.yaml` deployment manifest created

### Phase 4 - Target Prep
- [ ] Huawei Cloud Workspace desktop provisioned
- [ ] AD domain join verified
- [ ] Network access to staging share verified

### Phase 5 - Deployment
- [ ] MSI packages installed
- [ ] Installation logs reviewed for failures
- [ ] Reboot performed if any install returned 3010

### Phase 6 - User Data
- [ ] User documents copied
- [ ] Application settings copied
- [ ] Browser profiles migrated

### Phase 7 - Verification
- [ ] `scan_software.py --full` run on target
- [ ] Source vs. target comparison completed
- [ ] All critical applications verified present

### Phase 8 - Cutover
- [ ] User acceptance testing completed
- [ ] User signed off
- [ ] Source VDI powered off (grace period)

---

*Guide version: 1.0 - July 22, 2026*
*Skills: windows-software-inventory, windows-msi-inventory, msi-batch-installer*
*Strategy: Re-deploy (rebuild + data migration)*
*Target: Huawei Cloud Workspace*
