#!/usr/bin/env bash
set -euo pipefail

# format-findings.sh — Convert JSON findings to report formats
# Usage: format-findings.sh --format=<markdown|json|sarif|compliance>

FINDINGS_DIR="${FINDINGS_DIR:-/tmp/review-findings}"
FORMAT="markdown"

for arg in "$@"; do
  case "$arg" in
    --format=*) FORMAT="${arg#--format=}" ;;
    --help|-h)
      echo "Usage: $0 --format=<markdown|json|sarif|compliance>"
      exit 0
      ;;
  esac
done

case "$FORMAT" in
  markdown)
    echo "# Code Review and Security Findings"
    echo ""
    echo "Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo ""

    for findings_file in "${FINDINGS_DIR}"/*-findings.json; do
      [ -f "$findings_file" ] || continue
      echo "## $(basename "$findings_file" | sed 's/-findings.json//')"
      echo ""
      python3 -c "
import sys, json
try:
    findings = json.load(open('$findings_file'))
    if isinstance(findings, dict):
        findings = [findings]
    for f in findings:
        sev = f.get('severity', 'unknown')
        title = f.get('title', 'Untitled')
        file = f.get('file', 'unknown')
        line = f.get('line', '?')
        print(f'### [{f.get(\"id\", \"?\")}] {title}')
        print(f'- **File**: {file}:{line}')
        print(f'- **Severity**: {sev}')
        print(f'- **Category**: {f.get(\"category\", \"N/A\")}')
        print(f'- **Evidence**: \`{f.get(\"evidence\", \"N/A\")}\`')
        print(f'- **Remediation**: {f.get(\"remediation\", \"N/A\")}')
        print()
except Exception as e:
    print(f'Error parsing findings: {e}')
" 2>/dev/null || echo "No parseable findings in $findings_file"
    done
    ;;

  json)
    # Merge all findings into single JSON array
    python3 -c "
import json, glob, os
all_findings = []
for f in glob.glob('${FINDINGS_DIR}/*-findings.json'):
    try:
        data = json.load(open(f))
        if isinstance(data, list):
            all_findings.extend(data)
        else:
            all_findings.append(data)
    except: pass
print(json.dumps(all_findings, indent=2))
" 2>/dev/null || echo "[]"
    ;;

  sarif)
    # Convert to SARIF v2.1.0 format
    python3 -c "
import json, glob
all_findings = []
for f in glob.glob('${FINDINGS_DIR}/*-findings.json'):
    try:
        data = json.load(open(f))
        if isinstance(data, list): all_findings.extend(data)
        else: all_findings.append(data)
    except: pass
sarif = {
    'version': '2.1.0',
    'runs': [{
        'tool': {'driver': {'name': 'maas-code-review-and-security-skill', 'version': '1.0.0'}},
        'results': [{
            'ruleId': f.get('category', 'unknown'),
            'level': {'critical': 'error', 'high': 'error', 'medium': 'warning', 'low': 'note', 'info': 'note'}.get(f.get('severity', 'info'), 'note'),
            'message': {'text': f.get('title', '') + ': ' + f.get('description', '')},
            'locations': [{'physicalLocation': {'artifactLocation': {'uri': f.get('file', '')}, 'region': {'startLine': f.get('line', 1)}}}]
        } for f in all_findings]
    }]
}
print(json.dumps(sarif, indent=2))
" 2>/dev/null
    ;;

  compliance)
    echo "# Compliance Report"
    echo ""
    echo "Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo ""
    echo "## Summary"
    # Count findings by severity
    python3 -c "
import json, glob
all_findings = []
for f in glob.glob('${FINDINGS_DIR}/*-findings.json'):
    try:
        data = json.load(open(f))
        if isinstance(data, list): all_findings.extend(data)
        else: all_findings.append(data)
    except: pass
by_sev = {}
for f in all_findings:
    s = f.get('severity', 'unknown')
    by_sev[s] = by_sev.get(s, 0) + 1
print(f'Total findings: {len(all_findings)}')
for s in ['critical', 'high', 'medium', 'low', 'info']:
    print(f'  {s}: {by_sev.get(s, 0)}')
" 2>/dev/null
    echo ""
    echo "## Details"
    # Re-run markdown format for details
    "$0" --format=markdown
    ;;

  *)
    echo "ERROR: Unknown format: $FORMAT (use markdown, json, sarif, or compliance)" >&2
    exit 1
    ;;
esac
