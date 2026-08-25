# Huawei Cloud Request Signing (SDK-HMAC-SHA256)

## Algorithm Overview

Huawei Cloud APIs use `SDK-HMAC-SHA256` signing. This is **NOT** AWS SigV4 — there are no derived signing keys (no date/region/service derivation). The signature is a **single HMAC-SHA256** with the Secret Key (SK) as the key.

## Signing Steps

### 1. Build Canonical Request

```
CanonicalRequest = HTTPMethod + "\n" +
                   CanonicalURI + "\n" +
                   CanonicalQueryString + "\n" +
                   CanonicalHeaders + "\n" +
                   SignedHeaders + "\n" +
                   HashedRequestPayload
```

Where:
- `HTTPMethod` — `GET`, `POST`, `DELETE`, etc.
- `CanonicalURI` — URI path with **trailing slash** (e.g. `/apis/cci/v2/namespaces/`)
- `CanonicalQueryString` — empty for most CCI operations
- `CanonicalHeaders` — sorted headers, lowercase, colon-separated, each followed by `\n`
- `SignedHeaders` — semicolon-joined header names (without values)
- `HashedRequestPayload` — hex(SHA256(body_bytes))

### 2. Build String to Sign

```
StringToSign = "SDK-HMAC-SHA256" + "\n" +
               Timestamp + "\n" +
               HashedCanonicalRequest
```

Where:
- `Timestamp` — `YYYYMMDDTHHMMSSZ` format (UTC)
- `HashedCanonicalRequest` — hex(SHA256(CanonicalRequest))

### 3. Calculate Signature

```python
signature = HMAC-SHA256(SK, StringToSign).hexdigest()
```

**Single HMAC** — SK is used directly as the HMAC key. No key derivation chain.

### 4. Build Authorization Header

```
Authorization: SDK-HMAC-SHA256 Access=<AK>, SignedHeaders=<headers>, Signature=<signature>
```

## Required Headers

| Header | Value |
|--------|-------|
| `Content-Type` | `application/json` |
| `X-Project-Id` | Project ID for the region |
| `X-Sdk-Date` | Timestamp (`YYYYMMDDTHHMMSSZ`) |
| `Authorization` | `SDK-HMAC-SHA256 Access=..., SignedHeaders=..., Signature=...` |

`SignedHeaders` = `content-type;x-project-id;x-sdk-date` (sorted alphabetically, semicolon-separated)

## Python Implementation

```python
import hashlib
import hmac
import json
from datetime import datetime, timezone

def sign_request(ak, sk, project_id, method, path, body=None):
    # Body hash
    body_bytes = json.dumps(body).encode("utf-8") if body else b""
    body_hash = hashlib.sha256(body_bytes).hexdigest() if body else \
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    # Timestamp
    now = datetime.now(timezone.utc)
    sdk_date = now.strftime("%Y%m%dT%H%M%SZ")

    # Canonical request
    signed_headers = "content-type;x-project-id;x-sdk-date"
    canonical_uri = path + "/"  # trailing slash required
    canonical_headers = (
        f"content-type:application/json\n"
        f"x-project-id:{project_id}\n"
        f"x-sdk-date:{sdk_date}\n"
    )
    canonical_request = (
        f"{method}\n{canonical_uri}\n\n"
        f"{canonical_headers}\n{signed_headers}\n{body_hash}"
    )

    # String to sign
    hash_cr = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = f"SDK-HMAC-SHA256\n{sdk_date}\n{hash_cr}"

    # Signature (single HMAC, SK as key)
    signature = hmac.new(
        sk.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    # Auth header
    auth = (
        f"SDK-HMAC-SHA256 Access={ak}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    return {
        "Content-Type": "application/json",
        "X-Project-Id": project_id,
        "X-Sdk-Date": sdk_date,
        "Authorization": auth,
    }, body_bytes
```

## Common Pitfalls

1. **Trailing slash** — CanonicalURI MUST end with `/`. Without it, signature mismatch.
2. **Empty body hash** — When body is empty, use `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` (SHA256 of empty string).
3. **Header sorting** — Headers must be sorted alphabetically: `content-type` < `x-project-id` < `x-sdk-date`.
4. **No derived keys** — Unlike AWS SigV4, there is no `kDate`, `kRegion`, `kService` derivation. Use SK directly.
5. **Timestamp format** — Must be `YYYYMMDDTHHMMSSZ` (e.g. `20260825T170000Z`), not ISO 8601 with colons.
6. **System clock** — If the system clock is significantly off, signatures will be rejected with 401.

## Reference

- SDK signer source: `huaweicloudsdkcore/signer/signer.py` (Python SDK)
- [Huawei Cloud API Signing Guide](https://support.huaweicloud.com/devg-sdk/sdk_05_0001.html)
