# Workspace Migration Package

Complete toolkit for migrating VDI desktops to Huawei Cloud Workspace using the re-deploy strategy (rebuild from scratch on the target and migrate user data).

Includes 3 skills for AI agents (Hermes, Claude Code, OpenCode, Codex), ready-to-use PowerShell and Python scripts, and a step-by-step migration guide.

---

## What These Skills Do and Why They Are Useful

### The Problem

When migrating a VDI desktop to the cloud, you need to reinstall all the software the user had. But:

- You don't have a complete list of what was installed (and you can't rely on what the user remembers)
- The original installers (.msi) are buried in `C:\Windows\Installer\` with random names like `22ca53.msi` -- there's no human way to know which is which
- Installing 50+ packages manually one by one is unfeasible
- You need to verify that the target ended up identical to the source

### The Solution: 3 Skills Covering the Complete Workflow

```
  INVENTORY           BACK UP             INSTALL             VERIFY
  (what's there?)     (the .msi files)    (on the target)     (is it the same?)
      |                    |                    |                    |
      v                    v                    v                    v
  Skill 1             Skill 2              Skill 3              Skill 1
  software-inv        msi-inventory        msi-batch-installer  software-inv
```

#### Skill 1: windows-software-inventory

**What it does:** Scans a Windows system and lists ALL installed software -- name, version, publisher, install date, uninstall command. Nothing slips through because it queries the 4 registry keys where Windows registers applications (HKLM + HKCU, 64-bit + 32-bit).

**Why it's better than other methods:**
- `Win32_Product` (WMI) is very slow (10-60s) and also dangerous -- it can reconfigure MSI packages during the scan. Microsoft themselves warn against it.
- Manually checking "Add or Remove Programs" is slow and incomplete (doesn't show per-user apps, doesn't show 32-bit on 64-bit systems).
- This skill uses the registry directly: instant, complete, safe.

**What it produces:** A CSV and JSON with all applications, ready to classify and compare.

#### Skill 2: windows-msi-inventory

**What it does:** Finds the .msi installers Windows has cached in `C:\Windows\Installer\` (with random hex names), maps them to the corresponding software via the registry, reads their properties (ProductCode, UpgradeCode, Manufacturer), and backs them up with readable names.

**Why it's necessary:**
- You can't just copy `C:\Windows\Installer\*.msi` because you don't know what each file is.
- Some original .msi files may still be in the download directory (`InstallSource`) with their real names -- the skill also looks for them.
- Without this backup, you'd have to download each installer again from the vendor's website.

**What it produces:** A folder with all third-party .msi files renamed readably (e.g., `7_Zip_26_01_x64.msi`), plus a CSV with the manifest.

#### Skill 3: msi-batch-installer

**What it does:** Installs a batch of .msi files silently (without user interaction) using `msiexec`, with full logging, error code decoding, and a pass/fail report at the end.

**Why it's better than installing manually:**
- Installs 50 packages in minutes vs. hours by hand.
- Each installation generates a verbose log in `%TEMP%\msi-install-logs\` for debugging.
- Decodes error codes (1603 = permissions, 1618 = another installation in progress, 3010 = reboot needed).
- Continues with the next package if one fails (configurable).
- Provides both CMD and PowerShell scripts with elevation helpers.

**What it produces:** All software installed on the target + success/failure report per package.

---

## What This Package Includes

```
workspace-migration/
|
|-- skills/                          The 3 skills (SKILL.md + scripts)
|   |-- windows-software-inventory/
|   |   |-- SKILL.md
|   |   +-- scripts/scan_software.py
|   |-- windows-msi-inventory/
|   |   |-- SKILL.md
|   |   +-- scripts/scan_msi_installers.py
|   +-- msi-batch-installer/
|       |-- SKILL.md
|       +-- scripts/install-msi.ps1, install-msi.cmd
|
|-- msi-installer/                   Structured installation workflow
|   |-- scripts/
|   |   |-- 00_env_check.ps1         Verifies prerequisites
|   |   |-- 01_discover_msi.ps1      Discovers .msi in the directory
|   |   |-- 02_install_msi.ps1       Installs in batch
|   |   +-- 03_verify_install.ps1    Verifies everything was installed
|   |-- lib/
|   |   |-- msi_utils.ps1            MSI utility functions
|   |   +-- report_utils.ps1         JSON reporting functions
|   |-- configs/
|   |   +-- install.yaml             Config (UI mode, props, log dir)
|   +-- examples/
|       |-- run-elevated.ps1         Helper to elevate to Admin
|       +-- run-elevated-cmd.ps1     Helper to elevate (CMD)
|
|-- VDI-to-Huawei-Cloud-Workspace-Migration-Guide.md   Complete guide, 8 phases
+-- README.md                        (this file)
```

---

## Installation

The skills are markdown documents (SKILL.md) with YAML frontmatter + instructions. Each AI agent loads them from its own path. The scripts accompany each skill in its directory.

### Option A: Hermes Agent

Hermes loads skills from `~/.hermes/skills/<category>/<name>/`. The skills are already installed there (package installed on 2026-07-22). If you need to reinstall:

```bash
# Copy the 3 skills to the Hermes directory
cp -r skills/software-development/windows-software-inventory ~/.hermes/skills/software-development/
cp -r skills/software-development/windows-msi-inventory      ~/.hermes/skills/software-development/
cp -r skills/software-development/msi-batch-installer        ~/.hermes/skills/software-development/

# Verify they are available
hermes skills list | grep -E 'windows|msi'

# Load a skill in the current session
/skill windows-software-inventory
```

### Option B: Claude Code

Claude Code reads `CLAUDE.md` or `AGENTS.md` files from the working directory. To use these skills:

```bash
# Copy the SKILL.md files to the project directory
mkdir -p ~/.claude/skills
cp skills/software-development/windows-software-inventory/SKILL.md ~/.claude/skills/windows-software-inventory.md
cp skills/software-development/windows-msi-inventory/SKILL.md      ~/.claude/skills/windows-msi-inventory.md
cp skills/software-development/msi-batch-installer/SKILL.md        ~/.claude/skills/msi-batch-installer.md

# Or place an AGENTS.md in the project that references the skills
echo "See skills/ directory for migration procedures." > AGENTS.md
```

The scripts (scan_software.py, scan_msi_installers.py, install-msi.ps1) are used directly from the project directory -- the agent executes them with `python` or `powershell`.

### Option C: OpenCode

OpenCode uses `AGENTS.md` and loads skills from its config directory:

```bash
# Copy skills
mkdir -p ~/.opencode/skills
cp -r skills/software-development/windows-software-inventory ~/.opencode/skills/
cp -r skills/software-development/windows-msi-inventory      ~/.opencode/skills/
cp -r skills/software-development/msi-batch-installer        ~/.opencode/skills/
```

### Option D: OpenAI Codex

Codex CLI reads `AGENTS.md` from the repo. Copy the project and scripts to the working directory:

```bash
# Codex executes commands from the directory -- it just needs access to the scripts
cp -r workspace-migration /path/to/project/
cd /path/to/project/workspace-migration
# Codex will read AGENTS.md and can execute the scripts directly
```

### Option E: Any agent (generic usage)

The skills are just documentation + scripts. You can use them without any agent:

```powershell
# Phase 1: Inventory
python scripts/scan_software.py --full --json inventory.json --csv inventory.csv

# Phase 2: Back up MSI
python scripts/scan_msi_installers.py --backup "C:\Backup\msi" --props

# Phase 5: Install
powershell -File msi-installer/scripts/02_install_msi.ps1
```

---

## How to Use the Skills with an AI Agent

### Natural Triggers (what to tell the agent)

The agent will automatically load the appropriate skill when it detects intent. These are the prompts that activate each skill:

#### To inventory software (Skill 1)

```
"Scan the source VDI to list all installed software"
"Do a complete inventory of programs on this Windows machine"
"What software is installed on this computer? Export to CSV"
"Compare software on source VDI vs target"
```

#### To back up MSI installers (Skill 2)

```
"Find and back up all third-party MSI installers"
"Extract the cached .msi files in C:\Windows\Installer with their real names"
"Back up MSI installers for migration"
"Read properties (ProductCode, UpgradeCode) of installed MSI files"
```

#### To install in batch (Skill 3)

```
"Install all .msi files in the staging directory silently"
"Run the complete MSI installation workflow on the target"
"Install MSI packages in batch with logging"
"Run the workflow: env check, discover, install, verify"
```

#### For the complete migration

```
"Run the complete VDI to Huawei Cloud migration"
"Follow the migration guide step by step"
"Do the re-deploy: inventory, back up, install, verify"
```

### Structured Workflow (scripts in order)

If you prefer to run the workflow step by step with the structured scripts:

```powershell
# 0. Verify environment (admin, msiexec, config, disk space)
.\msi-installer\scripts\00_env_check.ps1

# 1. Discover .msi in the staging directory
$env:MSI_DIR = "\\staging-server\migration\msi-backup"
.\msi-installer\scripts\01_discover_msi.ps1

# 2. Install (requires approval: create empty file)
mkdir approvals; touch approvals\APPROVED_INSTALL
.\msi-installer\scripts\02_install_msi.ps1

# 3. Verify installation
.\msi-installer\scripts\03_verify_install.ps1
```

Each step generates a JSON report in `msi-installer/reports/`.

---

## Migration Workflow (Summary)

The complete guide is in `VDI-to-Huawei-Cloud-Workspace-Migration-Guide.md` (8 phases). Summary:

```
Phase 1: INVENTORY     Scan source VDI              -> source_inventory.csv
         |              Skill: windows-software-inventory
         v
Phase 2: BACK UP       Extract cached .msi           -> msi-backup/
         |              Skill: windows-msi-inventory
         v
Phase 3: PACKAGE       Organize in staging share     -> staging/
         |
         v
Phase 4: PREPARE       Provision clean target        -> Huawei Cloud desktop
         |
         v
Phase 5: INSTALL       Install .msi in batch         -> install logs
         |              Skill: msi-batch-installer
         v
Phase 6: MIGRATE DATA  Copy profiles and files       -> user-data/
         |
         v
Phase 7: VERIFY        Compare source vs target      -> parity report
         |              Skill: windows-software-inventory
         v
Phase 8: CUTOVER       UAT, sign-off, decommission
```

---

## Quick Reference Scripts

### scan_software.py (Skill 1)

```bash
python scan_software.py --full --json out.json --csv out.csv   # Full inventory
python scan_software.py --search "Python"                       # Search specific
python scan_software.py --full                                   # Include Store + Chocolatey
```

### scan_msi_installers.py (Skill 2)

```bash
python scan_msi_installers.py --props                            # List MSI + properties
python scan_msi_installers.py --backup "C:\Backup"              # Back up .msi files
python scan_msi_installers.py --extract "C:\Extracted"          # Extract contents
python scan_msi_installers.py --all                              # Include Microsoft products
```

### install-msi.ps1 (Skill 3)

```powershell
.\install-msi.ps1 -Path "C:\Packages"                           # Install all in dir
.\install-msi.ps1 -Path "app1.msi","app2.msi"                   # Install specific files
.\install-msi.ps1 -Path "C:\Packages" -UiMode basic             # With progress bar
.\install-msi.ps1 -Path "C:\Packages" -ContinueOnError:$false   # Stop on first error
```

---

## Requirements

| Component | Requirement |
|------------|-----------|
| Source VDI | Windows 10/11, PowerShell 3.0+, Python 3.11+, Admin access |
| Target | Huawei Cloud Workspace (Windows) |
| Staging | SMB share accessible from both source and target |
| AI Agent | Hermes / Claude Code / OpenCode / Codex (optional) |

---

## Common msiexec Error Codes

| Code | Meaning | Action |
|--------|-------------|--------|
| 0 | Success | -- |
| 1602 | User cancelled | Check UI mode |
| 1603 | Fatal error | Permissions or locked files -- run as Admin |
| 1618 | Another installation in progress | Wait and retry |
| 1619 | MSI cannot open | Missing or corrupt file |
| 1638 | Another version already installed | Uninstall existing version first |
| 3010 | Success but reboot required | Reboot and continue |

---

*Version: 1.0 -- July 2026*
*Skills: windows-software-inventory, windows-msi-inventory, msi-batch-installer*
*Strategy: Re-deploy (rebuild + data migration)*
*Target: Huawei Cloud Workspace*
