---
name: windows-software-inventory
description: Scan and enumerate all installed software on Windows systems via registry queries, Get-Package, and CIM/WMI. Includes ready-to-use PowerShell and Python scripts for inventory, export, and auditing.
---

# Windows Software Inventory

Scan installed software on Windows by querying the registry Uninstall keys — the reliable, fast, and comprehensive method. Also covers `Get-Package` and CIM/WMI as alternatives.

## Why Registry Queries (Not Win32_Product)

| Method | Speed | Completeness | Recommendation |
|--------|-------|-------------|----------------|
| Registry (Uninstall keys) | Fast (<1s) | All registered apps | **Primary method** |
| `Get-Package` | Fast | Same as registry (uses it internally) | Good alternative |
| `Win32_Product` / CIM | Very slow (10-60s+) | Only MSI-installed apps | Avoid — see pitfalls |
| `wmic product` | Very slow | Only MSI-installed apps | Deprecated, avoid |

**Key insight**: `Win32_Product` triggers the MSI provider which reconfigures (re-evaluates) every installed MSI package. Microsoft's own KB974524 warns this can cause side effects. The registry method is instant and safe.

## The Four Registry Locations

On a 64-bit Windows system, installed software is registered in up to **four** registry locations:

```
HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*          # 64-bit machine-wide
HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*  # 32-bit machine-wide
HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*          # 64-bit per-user
HKCU\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*  # 32-bit per-user (rare)
```

**You must check ALL of them** to get a complete picture. Missing WOW6432Node misses 32-bit apps (browsers, older software). Missing HKCU misses per-user installs (Zed, Insomnia, etc.).

### Useful Registry Values per Entry

| Value | Description | Present? |
|-------|-------------|----------|
| `DisplayName` | Software name | ~100% (filter on this) |
| `DisplayVersion` | Version string | ~95% |
| `Publisher` | Vendor/publisher | ~98% |
| `InstallDate` | YYYYMMDD format | ~40% |
| `InstallLocation` | Install directory path | ~17% |
| `UninstallString` | Uninstall command | ~100% |
| `QuietUninstallString` | Silent uninstall command | ~10% |
| `URLInfoAbout` | Vendor info URL | ~16% |
| `SystemComponent` | If 1, hide from UI (filter these) | varies |

## Method 1: PowerShell (Recommended for quick scans)

### Basic — all four locations, deduplicated

```powershell
$paths = @(
    'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
    'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
    'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
    'HKCU:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
)
$all = foreach ($p in $paths) {
    Get-ItemProperty $p -ErrorAction SilentlyContinue |
    Where-Object { $_.DisplayName -and -not $_.SystemComponent } |
    Select-Object DisplayName, DisplayVersion, Publisher, InstallDate,
                  InstallLocation, UninstallString,
                  @{N='RegistrySource';E={$p -replace '\*',''}}
}
$all | Sort-Object DisplayName -Unique
```

### Export to CSV

```powershell
$all | Sort-Object DisplayName -Unique |
    Export-Csv -Path "$env:USERPROFILE\installed_software.csv" -NoTypeInformation -Encoding UTF8
```

### Export to JSON

```powershell
$all | Sort-Object DisplayName -Unique |
    ConvertTo-Json -Depth 2 |
    Out-File -FilePath "$env:USERPROFILE\installed_software.json" -Encoding UTF8
```

### Search for specific software

```powershell
$all | Where-Object { $_.DisplayName -match 'Python|Git|Docker' }
```

### Filter system components / updates

```powershell
# Exclude system components, security updates, and KB patches
$all | Where-Object {
    -not $_.SystemComponent -and
    $_.DisplayName -notmatch '^(KB\d+|Security Update|Cumulative Update|Update for)'
}
```

## Method 2: Python winreg (Recommended for scripts/automation)

```python
import winreg, json, csv

hives = [
    (winreg.HKEY_LOCAL_MACHINE, 'HKLM-64', winreg.KEY_READ | winreg.KEY_WOW64_64KEY),
    (winreg.HKEY_LOCAL_MACHINE, 'HKLM-32', winreg.KEY_READ | winreg.KEY_WOW64_32KEY),
    (winreg.HKEY_CURRENT_USER, 'HKCU-64', winreg.KEY_READ | winreg.KEY_WOW64_64KEY),
    (winreg.HKEY_CURRENT_USER, 'HKCU-32', winreg.KEY_READ | winreg.KEY_WOW64_32KEY),
]

UNINSTALL_PATH = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'
FIELDS = ['DisplayName', 'DisplayVersion', 'Publisher', 'InstallDate',
          'InstallLocation', 'UninstallString', 'QuietUninstallString', 'URLInfoAbout']

def scan_installed_software():
    """Scan all registry Uninstall keys and return deduplicated software list."""
    results = []
    for hive, label, flag in hives:
        try:
            key = winreg.OpenKey(hive, UNINSTALL_PATH, 0, flag)
        except FileNotFoundError:
            continue
        count = winreg.QueryInfoKey(key)[0]
        for i in range(count):
            entry = {'_source': label}
            try:
                subkey_name = winreg.EnumKey(key, i)
                subkey = winreg.OpenKey(key, subkey_name)
            except FileNotFoundError:
                continue
            for f in FIELDS:
                try:
                    entry[f] = winreg.QueryValueEx(subkey, f)[0]
                except FileNotFoundError:
                    entry[f] = ''
            if entry.get('DisplayName') and not entry.get('SystemComponent'):
                results.append(entry)
    seen = set()
    unique = []
    for r in results:
        name = r['DisplayName']
        if name not in seen:
            seen.add(name)
            unique.append(r)
    unique.sort(key=lambda x: x['DisplayName'].lower())
    return unique
```

## Method 3: Get-Package (Simple alternative)

```powershell
Get-Package | Select-Object Name, Version, ProviderName | Sort-Object Name
```

## Method 4: CIM/WMI (Use with caution)

```powershell
# Win32_Product — SLOW, only MSI apps, may trigger reconfiguration
Get-CimInstance -ClassName Win32_Product | Select-Object Name, Version, Vendor, InstallDate
```

## Method 5: Windows Store / UWP Apps

```powershell
Get-AppxPackage | Select-Object Name, Version, Publisher | Sort-Object Name
```

## Method 6: Chocolatey packages (if installed)

```powershell
choco list --local-only
```

## Pitfalls

1. **WOW6432Node is critical on 64-bit Windows** — 32-bit apps register here. Skipping it misses a large portion of installed software.
2. **HKCU is per-user** — On a multi-user system, each user has their own HKCU Uninstall key.
3. **SystemComponent flag** — Filter entries with `SystemComponent=1` unless you want driver updates.
4. **Duplicate entries** — Always deduplicate by `DisplayName`.
5. **Not all software registers** — Portable apps and some custom installers don't write to the registry.
6. **Win32_Product is dangerous** — It can trigger MSI reconfiguration of packages.
7. **InstallDate format** — Stored as YYYYMMDD string, not a Unix timestamp.
8. **PowerShell from bash on Windows** — Use `powershell.exe -NoProfile -Command "..."` and escape `$` as `\$` inside double quotes.

## Verification

After running a scan, verify completeness:
- Compare count against `Settings > Apps > Installed apps` in Windows UI
- Check that well-known apps (browser, Office, etc.) appear
- Ensure both 32-bit and 64-bit entries are present
- Total count should typically be 100-300+ on a developer machine
