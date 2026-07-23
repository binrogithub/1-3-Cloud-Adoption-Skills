---
name: windows-msi-inventory
description: Find, extract, and back up MSI installers for third-party (non-system) applications on Windows. Covers registry LocalPackage discovery, MSI property reading via COM, admin extraction with msiexec /a, and backup workflows.
---

# Windows MSI Installer Inventory

Locate cached MSI installers for third-party applications, read their properties (ProductCode, UpgradeCode, etc.), extract their contents, and back them up.

## How Windows Stores MSI Files

When software is installed via Windows Installer (MSI), the original `.msi` file is **cached** in a hidden system folder:

```
C:\Windows\Installer\*.msi
```

The filename is **renamed to a random hex string** (e.g., `22ca53.msi`) with no obvious correlation to the original name. The mapping between installed software and its cached MSI is stored in the registry.

### Registry Structure

```
HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Installer\UserData\S-1-5-18\Products\{ProductKey}\
  └── InstallProperties\
        ├── DisplayName      → "7-Zip 26.01 (x64 edition)"
        ├── DisplayVersion   → "26.01.00.0"
        ├── Publisher        → "Igor Pavlov"
        ├── LocalPackage     → "C:\WINDOWS\Installer\22ca53.msi"   ← THE CACHED MSI
        └── InstallSource    → "D:\Downloads\"                      ← ORIGINAL INSTALL SOURCE DIR
```

- `S-1-5-18` = SYSTEM account (machine-wide installs)
- For per-user installs, replace with the user's SID (e.g., `S-1-5-21-...`)
- `{ProductKey}` = a registry-encoded GUID (packed format, not the standard `{GUID}`)

### The InstallSource Field

`InstallSource` records where the MSI was originally executed from. This can point to:
- **Downloads folder** — `D:\Users\...\Downloads\` (original `.msi` may still be there!)
- **Temp folder** — `C:\Users\...\AppData\Local\Temp\{GUID}\` (usually cleaned up after install)
- **Network share** — `\\server\share\packages\` (may still be accessible)
- **Program Files** — `C:\Program Files\...\InstallerCache\` (vendor-specific cache)

**Always check InstallSource** — the original named MSI (e.g., `7z2601-x64.msi`) may still exist there with a human-readable filename, which is more useful than the hex-renamed cache copy.

## Method 1: Find Third-Party MSI Installers (Python)

```python
import winreg, os

INSTALLER_PRODUCTS = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Installer\UserData\S-1-5-18\Products'

def get_msi_products():
    """Get all MSI products with LocalPackage paths from registry."""
    results = []
    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, INSTALLER_PRODUCTS, 0,
                         winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
    count = winreg.QueryInfoKey(key)[0]
    for i in range(count):
        try:
            subkey_name = winreg.EnumKey(key, i)
            product_key = winreg.OpenKey(key, subkey_name)
            install_props = winreg.OpenKey(product_key, 'InstallProperties')
            entry = {'product_key': subkey_name}
            for field in ['DisplayName', 'DisplayVersion', 'Publisher',
                          'LocalPackage', 'InstallSource']:
                try:
                    entry[field] = winreg.QueryValueEx(install_props, field)[0]
                except FileNotFoundError:
                    entry[field] = ''
            if entry.get('DisplayName') and entry.get('LocalPackage'):
                entry['msi_exists'] = os.path.exists(entry['LocalPackage'])
                if entry['msi_exists']:
                    entry['msi_size_mb'] = round(
                        os.path.getsize(entry['LocalPackage']) / (1024 * 1024), 1)
                results.append(entry)
        except FileNotFoundError:
            continue
    return results
```

## Method 2: Read MSI Properties via COM

The `WindowsInstaller.Installer` COM object lets you read any MSI property **without installing or modifying anything**.

```powershell
function Get-MSIProperty {
    param([string]$MsiPath, [string]$PropertyName)
    $installer = New-Object -ComObject WindowsInstaller.Installer
    $db = $installer.GetType().InvokeMember('OpenDatabase', 'InvokeMethod', $null, $installer, @($MsiPath, 0))
    $view = $db.GetType().InvokeMember('OpenView', 'InvokeMethod', $null, $db, @("SELECT Value FROM Property WHERE Property = '$PropertyName'"))
    $view.GetType().InvokeMember('Execute', 'InvokeMethod', $null, $view, $null)
    $record = $view.GetType().InvokeMember('Fetch', 'InvokeMethod', $null, $view, $null)
    if ($record) { $record.GetType().InvokeMember('StringData', 'GetProperty', $null, $record, 1) }
}
```

### Common MSI Properties

| Property | Description |
|----------|-------------|
| `ProductCode` | Unique GUID identifying the product |
| `ProductName` | Display name |
| `ProductVersion` | Version string |
| `Manufacturer` | Publisher/vendor |
| `ProductLanguage` | LCID (e.g., 1033 = English US) |
| `UpgradeCode` | GUID shared across versions of same product |
| `ALLUSERS` | 1 = machine-wide, empty = per-user |
| `INSTALLDIR` | Default install directory |

## Method 3: Extract MSI Contents (Admin Install)

`msiexec /a` performs an **administrative install** — it extracts all files from the MSI without actually installing the product.

```powershell
msiexec /a "C:\WINDOWS\Installer\22ca53.msi" /qn TARGETDIR="C:\Temp\extracted"
```

## Method 4: Back Up MSI Installers

Copy cached MSI files to a backup location with meaningful filenames:

```python
import shutil, re

def backup_msi_installers(output_dir, third_party_only=True):
    products = get_msi_products()
    if third_party_only:
        products = filter_third_party(products)
    os.makedirs(output_dir, exist_ok=True)
    for p in products:
        src = p['LocalPackage']
        if not os.path.exists(src):
            continue
        safe_name = re.sub(r'[^\w\-]', '_', p['DisplayName'])[:50]
        dst = os.path.join(output_dir, f'{safe_name}.msi')
        shutil.copy2(src, dst)
```

## Pitfalls

1. **C:\Windows\Installer is hidden and protected** — Never delete files from this folder.
2. **MSI filenames are hex-randomized** — You MUST go through the registry to map filenames to software names.
3. **Win32_Product triggers MSI reconfiguration** — Use the registry method instead.
4. **Not all software uses MSI** — EXE installers, portable apps, and Store apps don't have cached MSI files.
5. **InstallSource is often stale** — Always verify `os.path.exists()` before relying on it.
6. **Per-user vs machine-wide** — Machine-wide installs use SID `S-1-5-18`, per-user installs use the actual user SID.
7. **COM OpenDatabase mode 0 = read-only** — Always use mode 0 when reading MSI properties.
8. **msiexec /a requires elevation** — Admin install extraction needs admin privileges.
9. **Large MSIs** — Some cached MSIs can be hundreds of MB. Account for disk space when backing up.
10. **ProductKey format in registry** — The registry stores the ProductCode in a packed/swapped GUID format.

## Verification

After scanning, verify:
- All found MSI files exist at their `LocalPackage` paths
- MSI properties read via COM match the registry's DisplayName/Version
- Third-party filter excludes all Microsoft/system components
- Total size of MSIs is reasonable (typically 100MB–2GB for a developer machine)
- Check InstallSource directories for original named `.msi` files

## Related Skills

- `windows-software-inventory` — Scan ALL installed software (not just MSI) via registry Uninstall keys
