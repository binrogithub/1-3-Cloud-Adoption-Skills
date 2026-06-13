# Finding Format

## JSON Schema

Every finding must conform to this structure:

```json
{
  "id": "F-001",
  "file": "src/auth/handler.py",
  "line": 42,
  "column": 15,
  "severity": "high",
  "category": "OWASP-A07",
  "title": "Hardcoded API key in auth handler",
  "description": "MaaS API key is hardcoded instead of read from environment variable",
  "evidence": "Line 42: API_KEY = 'sk-...'",
  "remediation": "Replace with os.environ['MAAS_API_KEY'] and use env file with 0640 permissions",
  "persona": "security-auditor",
  "confidence": "high",
  "references": ["https://owasp.org/Top10/A07_2021-Identification_and_Authentication_Failures/"]
}
```

## Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | yes | Unique finding ID (F-NNN format, sequential per report) |
| file | string | yes | Relative file path from project root |
| line | integer | yes | Line number (1-indexed) |
| column | integer | no | Column number (1-indexed) |
| severity | enum | yes | critical, high, medium, low, info |
| category | string | yes | OWASP category code or custom category |
| title | string | yes | Short description (max 100 chars) |
| description | string | yes | Detailed explanation |
| evidence | string | yes | Code snippet or data proving the finding |
| remediation | string | yes | How to fix the finding |
| persona | enum | yes | code-reviewer or security-auditor |
| confidence | enum | no | high, medium, low (default: medium) |
| references | array | no | URLs for further reading |

## Severity Classification Rules

| Severity | Criteria | Merge Action |
|----------|----------|--------------|
| critical | Exploitable in production with no special access | Block merge immediately |
| high | Exploitable with some access or specific conditions | Block merge |
| medium | Security weakness but not directly exploitable | Warn, allow merge with documented acceptance |
| low | Best practice violation, minimal security impact | Info, allow merge |
| info | Observation, no security impact | Allow merge |

## Deduplication Rules

Two findings are duplicates if they share the same `file`, `line`, and `category`. When deduplicating:
- Keep the finding with higher severity
- Merge `evidence` fields
- Keep both `persona` values

## Report Formats

### Markdown

```markdown
## Security Findings

### [F-001] Hardcoded API key in auth handler
- **File**: src/auth/handler.py:42
- **Severity**: high
- **Category**: OWASP-A07
- **Evidence**: `API_KEY = 'sk-...'`
- **Remediation**: Use `os.environ['MAAS_API_KEY']`
```

### SARIF

Standard SARIF v2.1.0 format for GitHub Advanced Security integration.

### Compliance

Extended format with additional fields: `regulation`, `control`, `evidence_retention_days`.
