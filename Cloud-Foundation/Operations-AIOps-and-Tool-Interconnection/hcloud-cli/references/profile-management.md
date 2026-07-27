# Profile and Authentication Management

Configure KooCLI authentication profiles for accessing Huawei Cloud APIs.

## Quick setup

```bash
# Interactive setup (recommended for first-time)
hcloud configure init

# Test connectivity
hcloud configure test
```

## Profile operations

### Initialize (interactive)

```bash
hcloud configure init
```

Walks through setting up a profile with:
- Authentication mode (AKSK, ecsAgency, SSO)
- Access Key ID and Secret Access Key
- Region
- Project ID (optional)

### Set values

```bash
# Set AK/SK
hcloud configure set --access-key=YOUR_AK --secret-key=YOUR_SK

# Set region
hcloud configure set --region=la-north-2

# Set project ID
hcloud configure set --cli-project-id=PROJECT_ID

# Set domain ID (for agency/STS)
hcloud configure set --cli-domain-id=DOMAIN_ID

# Named profile
hcloud configure set --cli-profile=prod --access-key=PROD_AK --secret-key=PROD_SK --region=la-north-2
hcloud configure set --cli-profile=dev --access-key=DEV_AK --secret-key=DEV_SK --region=ap-southeast-1
```

### List profiles

```bash
hcloud configure list
```

Returns JSON with all profiles (secrets masked):

```json
{
  "current": "default",
  "profiles": [
    {
      "name": "default",
      "mode": "AKSK",
      "accessKeyId": "HPU****AWB",
      "secretAccessKey": "****",
      "region": "la-north-2"
    }
  ]
}
```

### Show current profile

```bash
hcloud configure show
```

### Delete a profile

```bash
hcloud configure delete --cli-profile=old-profile
```

### Clear all profiles

```bash
hcloud configure clear
```

### Test connectivity

```bash
hcloud configure test
```

Verifies that the current profile's credentials can authenticate with the cloud.

## Authentication modes

### AKSK (Access Key / Secret Key)

Default and most common mode. Requires an AK/SK pair from the Huawei Cloud console.

```bash
hcloud configure set --cli-mode=AKSK --access-key=YOUR_AK --secret-key=YOUR_SK --region=la-north-2
```

### Temporary AK/SK with Security Token

For temporary credentials (e.g., from STS or agency delegation):

```bash
hcloud configure set \
  --access-key=TEMP_AK \
  --secret-key=TEMP_SK \
  --cli-security-token=TEMP_TOKEN \
  --region=la-north-2
```

### ECS Agency Mode

When running on an ECS instance with an agency attached:

```bash
hcloud configure set --cli-mode=ecsAgency --region=la-north-2
```

No AK/SK needed — the CLI obtains temporary credentials from the instance metadata.

### SSO (Single Sign-On)

```bash
hcloud configure sso
```

Opens a browser for SSO authentication. After login, the CLI stores the session.

## Multi-profile usage

### Using `--cli-profile`

```bash
# Query prod
hcloud ECS ListServersDetails --cli-profile=prod --cli-region=la-north-2 --cli-output=json

# Query dev
hcloud ECS ListServersDetails --cli-profile=dev --cli-region=ap-southeast-1 --cli-output=json
```

### Environment variable

```bash
export HCLOUD_PROFILE=prod
hcloud ECS ListServersDetails --cli-region=la-north-2 --cli-output=json
```

## Region and project

### Region override

Region can be set at three levels (priority: CLI flag > profile > environment):

```bash
# CLI flag (highest priority)
hcloud ECS ListServersDetails --cli-region=eu-west-101

# Profile default
hcloud configure set --region=la-north-2

# Environment variable
export HCLOUD_REGION=la-north-2
```

### Common international regions

| Region code | Location |
|-------------|----------|
| `la-north-2` | Latin America - São Paulo |
| `ap-southeast-1` | Asia Pacific - Hong Kong |
| `ap-southeast-2` | Asia Pacific - Bangkok |
| `ap-southeast-3` | Asia Pacific - Singapore |
| `af-south-1` | Africa - Johannesburg |
| `eu-west-101` | Europe - Paris |
| `na-mexico-1` | North America - Mexico City |
| `tr-west-1` | Turkey - Istanbul |
| `me-east-1` | Middle East - Riyadh |

### Project ID

Project ID is typically auto-resolved from the region. Override when needed:

```bash
hcloud ECS ListServersDetails --cli-project-id=PROJECT_ID

# Or in profile
hcloud configure set --cli-project-id=PROJECT_ID
```

### Domain ID

For cross-account operations (agencies, STS):

```bash
hcloud ECS ListServersDetails --cli-domain-id=DOMAIN_ID
```

## Custom endpoint

For testing or private deployments:

```bash
hcloud ECS ListServersDetails --cli-endpoint=https://ecs.custom.example.com
```

## Timeouts and retries

```bash
# Connection timeout (default: 5s)
hcloud ECS ListServersDetails --cli-connect-timeout=10

# Read timeout (default: 10s)
hcloud ECS ListServersDetails --cli-read-timeout=30

# Retry count (0-5, default: 0)
hcloud ECS ListServersDetails --cli-retry-count=3
```

## SSL verification

```bash
# Skip SSL verification (not recommended, for self-signed certs only)
hcloud ECS ListServersDetails --cli-skip-secure-verify=true
```

## Best practices

1. **Use named profiles** — separate prod/dev/staging credentials.
2. **Never commit credentials** — AK/SK should be in environment variables or secret managers, not in scripts.
3. **Use ECS agency mode on ECS** — avoids storing long-term credentials on instances.
4. **Always `hcloud configure test`** after setup — verify before running operations.
5. **Keep region explicit** — especially for destructive operations, don't rely on defaults.
6. **Rotate AK/SK regularly** — delete old keys after rotation.
