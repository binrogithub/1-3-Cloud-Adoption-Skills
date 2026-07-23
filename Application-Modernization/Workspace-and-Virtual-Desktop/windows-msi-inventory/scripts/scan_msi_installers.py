#!/usr/bin/env python
"""
Windows MSI Installer Scanner
============================
Finds cached MSI installers for third-party (non-system) applications.
Can read MSI properties, back up installers, extract contents, and find original MSIs.

Usage:
    python scan_msi_installers.py                          # List third-party MSI installers
    python scan_msi_installers.py --all                    # Include Microsoft/system products
    python scan_msi_installers.py --props                  # Read MSI properties via COM
    python scan_msi_installers.py --backup "C:\\Backup"    # Backup MSI files to dir
    python scan_msi_installers.py --extract "C:\\Extracted" # Extract MSI contents via msiexec /a
    python scan_msi_installers.py --json out.json --csv out.csv  # Export results
"""

import winreg
import os
import re
import json
import csv
import shutil
import subprocess
import argparse
import sys
from datetime import datetime


# ── Registry Configuration ──────────────────────────────────────────────

INSTALLER_PRODUCTS = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Installer\UserData\S-1-5-18\Products'

SYSTEM_PATTERNS = [
    'Microsoft', 'Windows SDK', 'Visual C++', 'Office', 'Click-to-Run',
    'Application Verifier', 'Universal CRT', '.NET', 'Cumulative',
    'Security Update', 'Setup WMI', 'Desktop Extension', 'IoT Extension',
    'KBC', 'Extension SDK'
]

MSI_PROPERTIES = [
    'ProductCode', 'ProductName', 'ProductVersion', 'Manufacturer',
    'ProductLanguage', 'UpgradeCode'
]


# ── Registry Scanner ────────────────────────────────────────────────────

def get_msi_products():
    """Get all MSI products with LocalPackage paths from registry."""
    results = []
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, INSTALLER_PRODUCTS, 0,
                             winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
    except FileNotFoundError:
        return results

    count = winreg.QueryInfoKey(key)[0]
    for i in range(count):
        try:
            subkey_name = winreg.EnumKey(key, i)
            product_key = winreg.OpenKey(key, subkey_name)
            install_props = winreg.OpenKey(product_key, 'InstallProperties')
        except FileNotFoundError:
            continue

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
            else:
                entry['msi_size_mb'] = 0
            results.append(entry)

    results.sort(key=lambda x: x['DisplayName'].lower())
    return results


def get_user_sid():
    """Get current user's SID for per-user MSI products."""
    try:
        result = subprocess.run(
            ['powershell.exe', '-NoProfile', '-Command',
             '[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value'],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip()
    except Exception:
        return ''


def get_per_user_msi_products():
    """Get MSI products installed for the current user."""
    sid = get_user_sid()
    if not sid:
        return []
    path = f'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Installer\\UserData\\{sid}\\Products'
    results = []
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0,
                             winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
    except FileNotFoundError:
        return results

    count = winreg.QueryInfoKey(key)[0]
    for i in range(count):
        try:
            subkey_name = winreg.EnumKey(key, i)
            product_key = winreg.OpenKey(key, subkey_name)
            install_props = winreg.OpenKey(product_key, 'InstallProperties')
        except FileNotFoundError:
            continue

        entry = {'product_key': subkey_name, '_scope': 'per-user'}
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
            else:
                entry['msi_size_mb'] = 0
            results.append(entry)

    results.sort(key=lambda x: x['DisplayName'].lower())
    return results


def filter_third_party(products, exclude_patterns=None):
    """Filter out Microsoft/system products, keep third-party only."""
    if exclude_patterns is None:
        exclude_patterns = SYSTEM_PATTERNS
    third_party = []
    for p in products:
        publisher = p.get('Publisher', '')
        name = p.get('DisplayName', '')
        if not publisher:
            continue
        is_system = any(
            pat.lower() in publisher.lower() or pat.lower() in name.lower()
            for pat in exclude_patterns
        )
        if not is_system:
            third_party.append(p)
    third_party.sort(key=lambda x: x['DisplayName'].lower())
    return third_party


# ── MSI Property Reader (COM) ───────────────────────────────────────────

def get_msi_properties(msi_path):
    """Read MSI properties via WindowsInstaller.Installer COM object."""
    ps_path = msi_path.replace('\\', '\\\\')
    props_list = "','".join(MSI_PROPERTIES)
    ps_script = f"""
$installer = New-Object -ComObject WindowsInstaller.Installer
$db = $installer.GetType().InvokeMember('OpenDatabase', 'InvokeMethod', $null, $installer, @('{ps_path}', 0))
$props = @('{props_list}')
foreach ($p in $props) {{
    try {{
        $view = $db.GetType().InvokeMember('OpenView', 'InvokeMethod', $null, $db, @("SELECT Value FROM Property WHERE Property = '$p'"))
        $view.GetType().InvokeMember('Execute', 'InvokeMethod', $null, $view, $null)
        $record = $view.GetType().InvokeMember('Fetch', 'InvokeMethod', $null, $view, $null)
        if ($record) {{ Write-Output "$p=$($record.GetType().InvokeMember('StringData', 'GetProperty', $null, $record, 1))" }}
    }} catch {{}}
}}
"""
    try:
        result = subprocess.run(
            ['powershell.exe', '-NoProfile', '-Command', ps_script],
            capture_output=True, text=True, timeout=30
        )
        props = {}
        for line in result.stdout.strip().split('\n'):
            if '=' in line:
                k, v = line.split('=', 1)
                props[k.strip()] = v.strip()
        return props
    except Exception as e:
        return {'error': str(e)}


# ── Backup ──────────────────────────────────────────────────────────────

def backup_msi_installers(products, output_dir):
    """Copy cached MSI files to output_dir with meaningful names."""
    os.makedirs(output_dir, exist_ok=True)
    results = []
    for p in products:
        src = p.get('LocalPackage', '')
        if not src or not os.path.exists(src):
            results.append({**p, 'backup_status': 'missing', 'backup_path': ''})
            continue
        safe_name = re.sub(r'[^\w\-]', '_', p.get('DisplayName', 'unknown'))[:50]
        version = p.get('DisplayVersion', '')
        if version:
            ver_clean = re.sub(r'[^\w.]', '', version)
            safe_name += f'_v{ver_clean}'
        dst = os.path.join(output_dir, f'{safe_name}.msi')
        if os.path.exists(dst):
            base, ext = os.path.splitext(dst)
            dst = f"{base}_{os.path.basename(src)}{ext}"
        try:
            shutil.copy2(src, dst)
            results.append({
                **p,
                'backup_status': 'copied',
                'backup_path': dst,
                'backup_size_mb': round(os.path.getsize(dst) / (1024 * 1024), 1)
            })
        except Exception as e:
            results.append({**p, 'backup_status': f'error: {e}', 'backup_path': ''})
    return results


# ── Extract (msiexec /a) ────────────────────────────────────────────────

def extract_msi(msi_path, target_dir, timeout=120):
    """Extract MSI contents via admin install."""
    os.makedirs(target_dir, exist_ok=True)
    try:
        subprocess.run(
            ['msiexec', '/a', msi_path, '/qn', f'TARGETDIR={target_dir}'],
            check=True, timeout=timeout
        )
        return True
    except Exception:
        return False


# ── Find Original MSIs ──────────────────────────────────────────────────

def find_original_msi(install_source):
    """Look for original .msi files in the InstallSource directory."""
    if not install_source or not os.path.exists(install_source):
        return []
    try:
        return [
            os.path.join(install_source, f)
            for f in os.listdir(install_source)
            if f.lower().endswith('.msi')
        ]
    except Exception:
        return []


# ── Export ──────────────────────────────────────────────────────────────

def export_json(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  JSON exported: {path}")


def export_csv(products, path):
    columns = ['DisplayName', 'DisplayVersion', 'Publisher', 'LocalPackage',
               'msi_exists', 'msi_size_mb', 'InstallSource']
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(products)
    print(f"  CSV exported:  {path}")


# ── Main ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Windows MSI Installer Scanner')
    parser.add_argument('--all', action='store_true', help='Include Microsoft/system products')
    parser.add_argument('--props', action='store_true', help='Read MSI properties via COM')
    parser.add_argument('--backup', type=str, help='Backup MSI files to this directory')
    parser.add_argument('--extract', type=str, help='Extract MSI contents to this directory')
    parser.add_argument('--json', type=str, help='JSON output path')
    parser.add_argument('--csv', type=str, help='CSV output path')
    parser.add_argument('--search', type=str, help='Filter results by name (substring match)')
    args = parser.parse_args()

    print(f"=== Windows MSI Installer Scanner ===")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Scan
    print("[1] Scanning machine-wide MSI products...")
    products = get_msi_products()
    print(f"  Found {len(products)} MSI products")

    print("[2] Scanning per-user MSI products...")
    user_products = get_per_user_msi_products()
    print(f"  Found {len(user_products)} per-user MSI products")
    products.extend(user_products)

    # Filter
    if not args.all:
        print("\n[3] Filtering to third-party only...")
        products = filter_third_party(products)
        print(f"  {len(products)} third-party MSI products")

    # Search filter
    if args.search:
        search = args.search.lower()
        products = [p for p in products if search in p['DisplayName'].lower()]
        print(f"\n  Filtered by '{args.search}': {len(products)} matches")

    # Display
    print(f"\n{'='*80}")
    print(f"{'Name':<45s} {'Version':<14s} {'Size':>7s}  {'LocalPackage'}")
    print(f"{'='*80}")
    for p in products:
        name = p['DisplayName'][:44]
        ver = p.get('DisplayVersion', '\u2014')[:13]
        size = f"{p.get('msi_size_mb', 0):.1f}MB"
        lp = p.get('LocalPackage', '')
        exists = '\u2713' if p.get('msi_exists') else '\u2717'
        print(f"{name:<45s} {ver:<14s} {size:>7s}  {exists} {lp}")

    total_mb = sum(p.get('msi_size_mb', 0) for p in products)
    print(f"\nTotal: {len(products)} products, {total_mb:.1f}MB")

    # Read properties
    if args.props:
        print(f"\n[4] Reading MSI properties via COM...")
        for p in products:
            if p.get('msi_exists'):
                props = get_msi_properties(p['LocalPackage'])
                p['msi_properties'] = props
                print(f"\n  {p['DisplayName']}:")
                for k, v in props.items():
                    print(f"    {k}: {v}")

    # Backup
    if args.backup:
        print(f"\n[5] Backing up MSI files to {args.backup}...")
        products = backup_msi_installers(products, args.backup)
        copied = sum(1 for p in products if p.get('backup_status') == 'copied')
        backup_mb = sum(p.get('backup_size_mb', 0) for p in products if p.get('backup_status') == 'copied')
        print(f"  Copied: {copied}/{len(products)} files, {backup_mb:.1f}MB")

    # Extract
    if args.extract:
        print(f"\n[6] Extracting MSI contents to {args.extract}...")
        for p in products:
            if p.get('msi_exists'):
                safe_name = re.sub(r'[^\w\-]', '_', p['DisplayName'])[:30]
                target = os.path.join(args.extract, safe_name)
                print(f"  Extracting {p['DisplayName']}...")
                success = extract_msi(p['LocalPackage'], target)
                p['extracted'] = success
                print(f"    {'\u2713' if success else '\u2717'} {target}")

    # Check InstallSource for original MSIs
    print(f"\n[7] Checking InstallSource for original MSI files...")
    for p in products:
        orig = find_original_msi(p.get('InstallSource', ''))
        if orig:
            p['original_msi_files'] = orig
            print(f"  {p['DisplayName']}: found {len(orig)} original MSI(s) in {p['InstallSource']}")
            for f in orig:
                print(f"    -> {f}")

    # Export
    if args.json or args.csv:
        print(f"\nExporting...")
    if args.json:
        export_json(products, args.json)
    if args.csv:
        export_csv(products, args.csv)

    print(f"\nDone!")


if __name__ == '__main__':
    main()
