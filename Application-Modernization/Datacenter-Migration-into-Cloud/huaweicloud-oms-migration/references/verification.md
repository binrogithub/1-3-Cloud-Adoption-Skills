# Post-Migration Verification

Procedures to verify that an OMS migration completed successfully and all objects are intact in the destination OBS bucket.

## Step 1: Check Task Status

The `terraform output` command reads from the local state snapshot, which may be stale. Always refresh first.

```bash
# Refresh state to get live status from the OMS API
terraform refresh \
  -var="src_cloud_type=AWS" \
  -var="src_region=us-east-2" \
  -var="src_bucket=demo-bucket-17b5e8a2" \
  -var="src_ak=..." \
  -var="src_sk=..." \
  -var="hc_region=la-north-2" \
  -var="hc_bucket=demo-bucket-17b5e8a2" \
  -var="hc_ak=..." \
  -var="hc_sk=..."

# Read the refreshed status
terraform output oms_task_status
```

### Task status codes

| Code | Meaning | Action |
|------|---------|--------|
| `1` | Waiting to migrate | Task created but not started. Check `start_task = true`. |
| `2` | Migrating | In progress. Wait and re-check. |
| `3` | Migration paused | Paused via `action = "stop"`. Resume with `action = "start"`. |
| `4` | Migration failed | Check failed objects in `oms/` folder. See [troubleshooting.md](troubleshooting.md). |
| `5` | Migration succeeded | Proceed to object-level verification. |

For sync tasks (`oms_migration_sync_task`), status is `SYNCHRONIZING` or `STOPPED`.

## Step 2: Compare Object Counts

```bash
# Source (AWS S3)
aws s3api list-objects-v2 --bucket <src-bucket> --query 'KeyCount' --output text

# Destination (Huawei Cloud OBS)
hcloud obs ls obs://<dest-bucket>/ -d -s
# Look at the "File number: N" line at the bottom
```

The counts should match. If the destination has more objects, check for the `oms/` folder (OMS metadata, not source objects).

## Step 3: Compare ETags (Byte-Level Integrity)

ETags (MD5 checksums for non-multipart objects) should be identical between source and destination.

```bash
# Source ETags
aws s3api list-objects-v2 --bucket <src-bucket> \
  --query 'Contents[].{Key:Key,ETag:ETag,Size:Size}' \
  --output table

# Destination ETags
hcloud obs ls obs://<dest-bucket>/ -d
# The ETag column shows the checksum in quotes
```

Compare the ETag values for each object key. They must match exactly.

> **Note**: For objects uploaded via S3 multipart upload, the ETag is not a simple MD5 and may differ in format. In that case, compare object sizes instead, or use `crc64` consistency check if migrating from Aliyun/Tencent/HC.

## Step 4: Compare Object Sizes

```bash
# Source total size
aws s3api list-objects-v2 --bucket <src-bucket> \
  --query 'sum(Contents[].Size)' --output text

# Destination — sum the Size column from:
hcloud obs ls obs://<dest-bucket>/ -d
```

Total bytes should match.

## Step 5: Inspect the OMS Metadata Folder

OMS creates an `oms/` folder in the destination bucket containing migration metadata:

```bash
hcloud obs ls obs://<dest-bucket>/oms/ -d -s
```

| File | Meaning |
|------|---------|
| (empty folder) | No failed objects — migration clean |
| `failed_object_list.txt` | Objects that failed to migrate. Re-run the task or migrate these manually. |
| `success_object_list.txt` | Objects successfully migrated (if recording enabled). |

If the `oms/` folder contains a failed object list, investigate each failure and re-run the migration task (idempotent with `SIZE_LAST_MODIFIED_COMPARISON_OVERWRITE`).

## Step 6: Spot-Check Object Content (Optional)

For critical objects, download and compare checksums:

```bash
# Download from source
aws s3 cp s3://<src-bucket>/<key> /tmp/src-file

# Download from destination
hcloud obs cp obs://<dest-bucket>/<key> /tmp/dst-file

# Compare
md5sum /tmp/src-file /tmp/dst-file
```

## Step 7: Verify Metadata (If enable_metadata_migration = true)

```bash
# Source metadata
aws s3api head-object --bucket <src-bucket> --key <key> --query 'ContentType'

# Destination metadata
hcloud obs stat obs://<dest-bucket>/<key>
# Look for Content-Type
```

ContentType is always migrated (even if `enable_metadata_migration = false`). Custom metadata (x-amz-meta-*) is migrated only when `enable_metadata_migration = true`.

## Automated Verification Script

```bash
#!/bin/bash
SRC_BUCKET="demo-bucket-17b5e8a2"
DST_BUCKET="demo-bucket-17b5e8a2"

# Get source object list
aws s3api list-objects-v2 --bucket "$SRC_BUCKET" \
  --query 'Contents[].{Key:Key,ETag:ETag,Size:Size}' --output json > /tmp/src-objects.json

SRC_COUNT=$(jq 'length' /tmp/src-objects.json)
SRC_SIZE=$(jq '[.[].Size] | add' /tmp/src-objects.json)

# Get destination object list (parse obsutil output)
DST_INFO=$(hcloud obs ls "obs://$DST_BUCKET/" -d -s 2>&1)
DST_COUNT=$(echo "$DST_INFO" | grep "File number:" | grep -oP '\d+')

echo "Source:   $SRC_COUNT objects, $SRC_SIZE bytes"
echo "Dest:     $DST_COUNT objects"
echo "Match:    $([ "$SRC_COUNT" = "$DST_COUNT" ] && echo YES || echo NO)"
```

## Verification Checklist

- [ ] Task status = `5` (succeeded)
- [ ] Object count: source == destination
- [ ] ETags match for all objects
- [ ] Total size: source == destination
- [ ] `oms/` folder has no failed objects
- [ ] (If applicable) Metadata (ContentType, custom) matches
- [ ] (If applicable) Storage class matches or follows `dst_storage_policy`
