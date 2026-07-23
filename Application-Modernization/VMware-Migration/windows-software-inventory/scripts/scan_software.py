#!/usr/bin/env python
"""
Windows Software Inventory Scanner
==================================
Scans all registry Uninstall keys (4 locations) for installed software.
Exports to JSON and CSV. Optionally includes UWP Store apps and Chocolatey packages.

Usage:
    python scan_software.py                    # Print summary + export JSON+CSV
    python scan_software.py --json out.json    # Custom JSON path
    python scan_software.py --csv out.csv      # Custom CSV path
    python scan_software.py --full             # Include Store apps + Chocolatey
    python scan_software.py --search "Python"  # Filter by name
"""

import winreg
import json
import csv
import argparse
import subprocess
import sys
from datetime import datetime


# ── Registry Configuration ──────────────────────────────────────────────

HIVES = [
    (winreg.HKEY_LOCAL_MACHINE, 'HKLM-64', winreg.KEY_READ | winreg.KEY_WOW64_64KEY),
    (winreg.HKEY_LOCAL_MACHINE, 'HKLM-32', winreg.KEY_READ | winreg.KEY_WOW64_32KEY),
    (winreg.HKEY_CURRENT_USER, 'HKCU-64', winreg.KEY_READ | winreg.KEY_WOW64_64KEY),
    (winreg.HKEY_CURRENT_USER, 'HKCU-32', winreg.KEY_READ | winreg.KEY_WOW64_32KEY),
]

UNINSTALL_PATH = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'

FIELDS = [
    'DisplayName', 'DisplayVersion', 'Publisher', 'InstallDate',
    'InstallLocation', 'UninstallString', 'QuietUninstallString',
    'URLInfoAbout', 'SystemComponent', 'NoModify', 'NoRemove', 'NoRepair'
]


# ── Registry Scanner ────────────────────────────────────────────────────

def scan_registry():
    """Scan all 4 registry Uninstall key locations. Returns deduplicated list."""
    results = []

    for hive, label, flag in HIVES:
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
                    val = winreg.QueryValueEx(subkey, f)[0]
                    entry[f] = str(val) if not isinstance(val, int) else val
                except FileNotFoundError:
                    entry[f] = '' if f != 'SystemComponent' else 0

            # Only include entries with a DisplayName that aren't hidden system components
            if entry.get('DisplayName') and not entry.get('SystemComponent'):
                results.append(entry)

    # Deduplicate by DisplayName (keep first occurrence)
    seen = set()
    unique = []
    for r in results:
        name = r['DisplayName']
        if name not in seen:
            seen.add(name)
            unique.append(r)

    unique.sort(key=lambda x: x['DisplayName'].lower())
    return unique


# ── UWP Store Apps ──────────────────────────────────────────────────────

def scan_store_apps():
    """Scan UWP/Store apps via PowerShell Get-AppxPackage."""
    try:
        result = subprocess.run(
            ['powershell.exe', '-NoProfile', '-Command',
             'Get-AppxPackage | Select-Object Name, Version, Publisher, PackageFullName | ConvertTo-Json -Depth 2'],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            return data if isinstance(data, list) else [data]
    except (Exception,):
        pass
    return []


# ── Chocolatey ──────────────────────────────────────────────────────────

def scan_chocolatey():
    """Scan Chocolatey packages if choco is installed."""
    try:
        result = subprocess.run(
            ['choco', 'list', '--local-only', '-r'],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0 and result.stdout.strip():
            packages = []
            for line in result.stdout.strip().split('\n'):
                parts = line.split('|')
                if len(parts) >= 2:
                    packages.append({'Name': parts[0], 'Version': parts[1]})
            return packages
    except FileNotFoundError:
        pass
    return []


# ── Export ──────────────────────────────────────────────────────────────

def export_json(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  JSON exported: {path}")


def export_csv(software, path):
    columns = ['DisplayName', 'DisplayVersion', 'Publisher', 'InstallDate',
               'InstallLocation', 'UninstallString', '_source']
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(software)
    print(f"  CSV exported:  {path}")


# ── Main ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Windows Software Inventory Scanner')
    parser.add_argument('--json', default='installed_software.json', help='JSON output path')
    parser.add_argument('--csv', default='installed_software.csv', help='CSV output path')
    parser.add_argument('--full', action='store_true', help='Include Store apps + Chocolatey')
    parser.add_argument('--search', type=str, help='Filter results by name (substring match)')
    args = parser.parse_args()

    print(f"=== Windows Software Inventory ===")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Registry scan
    print("[1/3] Scanning registry Uninstall keys...")
    software = scan_registry()
    print(f"  Found {len(software)} unique applications")

    report = {'scan_date': datetime.now().isoformat(), 'registry': software}

    if args.full:
        print("\n[2/3] Scanning UWP Store apps...")
        store = scan_store_apps()
        print(f"  Found {len(store)} Store apps")
        report['store_apps'] = store

        print("\n[3/3] Scanning Chocolatey packages...")
        choco = scan_chocolatey()
        print(f"  Found {len(choco)} Chocolatey packages")
        report['chocolatey'] = choco

        total = len(software) + len(store) + len(choco)
        print(f"\n=== Total: {total} packages ===")
    else:
        print(f"\n=== Total: {len(software)} applications ===")

    # Filter
    if args.search:
        search = args.search.lower()
        software = [s for s in software if search in s['DisplayName'].lower()]
        print(f"\nFiltered by '{args.search}': {len(software)} matches")
        for s in software:
            print(f"  {s['DisplayName']} v{s.get('DisplayVersion', '?')} ({s.get('Publisher', '?')})")

    # Export
    print(f"\nExporting...")
    export_json(report, args.json)
    export_csv(software, args.csv)
    print(f"\nDone!")


if __name__ == '__main__':
    main()
