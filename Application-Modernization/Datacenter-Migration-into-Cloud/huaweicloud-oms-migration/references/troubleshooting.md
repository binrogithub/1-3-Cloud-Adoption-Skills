# Troubleshooting OMS Migration

Common errors encountered during OMS object storage migration and their solutions.

---

## OMS.0064 — Invalid request parameters [description] invalid.

**Symptom**: `terraform apply` fails with:
```
error_code: OMS.0064
error_msg: Invalid request parameters.
error_detail: request parameter [description] invalid.
```

**Cause**: The `description` field contains characters that OMS rejects. The API does not accept arrow operators (`->`, `<-`, `=>`), comparison operators (`<=`, `>=`, `<>`), or some non-ASCII characters.

**Solution**: Use plain ASCII in the description. Replace `->` with `to`:
```hcl
# BAD
description = "AWS S3 -> Huawei OBS migration"

# GOOD
description = "AWS S3 to Huawei OBS migration"
```

---

## Provider Error — ECS Metadata API timeout

**Symptom**: `terraform plan` fails with:
```
Error fetching Auth credentials from ECS Metadata API, AkSk or ECS agency must be provided:
Error requesting metadata API: Get "http://169.254.169.254/openstack/latest/securitykey": dial tcp 169.254.169.254:80: i/o timeout
```

**Cause**: The `huaweicloud` Terraform provider is trying to use the ECS IMDS to fetch credentials (like the AWS provider would), but no ECS metadata service is available.

**Solution**: Explicitly set `access_key` and `secret_key` in the provider block:
```hcl
provider "huaweicloud" {
  region     = var.hc_region
  access_key = var.hc_ak
  secret_key = var.hc_sk
}
```

Or export environment variables:
```bash
export HW_ACCESS_KEY="<your-ak>"
export HW_SECRET_KEY="<your-sk>"
```

---

## Bucket Name Collision

**Symptom**: `terraform apply` fails when creating `huaweicloud_obs_bucket` with a 409 or "bucket already exists" error.

**Cause**: OBS bucket names are globally unique within a region. The chosen name is already taken by another account.

**Solution**: Choose a different name. Add a suffix or random string:
```hcl
resource "huaweicloud_obs_bucket" "dest" {
  bucket = "${var.hc_bucket}-oms"  # or add random suffix
  acl    = "private"
}
```

If the bucket exists in your own account and you want to reuse it, switch to a `data` block:
```hcl
data "huaweicloud_obs_bucket" "dest" {
  bucket = var.hc_bucket
}
```

---

## AccessDenied on Source Bucket

**Symptom**: OMS task status = `4` (failed). The `oms/` folder shows all objects as failed with `AccessDenied`.

**Cause**: The source AK/SK lacks `s3:GetObject` or `s3:ListBucket` permission on the source bucket.

**Solution**: Attach a policy granting read access:
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["s3:ListBucket", "s3:GetObject"],
    "Resource": [
      "arn:aws:s3:::<bucket>",
      "arn:aws:s3:::<bucket>/*"
    ]
  }]
}
```

For buckets with KMS encryption, also grant `kms:Decrypt` on the KMS key.

---

## Task Status Stuck at 2 (Migrating)

**Symptom**: `terraform output oms_task_status` always returns `2`, even after waiting.

**Cause**: `terraform output` reads from the local state file, which is a snapshot from apply time. It does not query the live OMS API.

**Solution**: Refresh the state before reading the output:
```bash
terraform refresh -var=...  # pass all vars
terraform output oms_task_status
```

Or use `terraform apply -refresh-only` to update state without making changes.

For long migrations, poll with a loop:
```bash
while true; do
  terraform refresh -var=... 2>/dev/null
  STATUS=$(terraform output -raw oms_task_status)
  echo "Status: $STATUS"
  [ "$STATUS" = "5" ] || [ "$STATUS" = "4" ] && break
  sleep 30
done
```

---

## Archive Objects Not Migrated

**Symptom**: Some objects show as skipped or failed. Source bucket contains GLACIER/ARCHIVE/DEEP_ARCHIVE storage class objects.

**Cause**: Archive objects must be restored before they can be read. OMS does not restore them by default.

**Solution**: Set `enable_restore = true` on the OMS task:
```hcl
resource "huaweicloud_oms_migration_task" "migration" {
  enable_restore = true
  # ...
}
```

This tells OMS to automatically initiate restore and wait for completion before migrating. Note: restore can take hours and incurs source-cloud costs.

---

## Tencent COS — Missing app_id

**Symptom**: Task creation fails with an error about missing APP ID when `src_cloud_type = Tencent`.

**Cause**: Tencent COS requires an APP ID in addition to AK/SK.

**Solution**: Add the `app_id` parameter:
```hcl
source_object {
  data_source = "Tencent"
  app_id      = "1250000000"  # Tencent APP ID
  region      = "ap-guangzhou"
  bucket      = "my-bucket-1250000000"
  access_key  = var.src_ak
  secret_key  = var.src_sk
  object      = [""]
}
```

---

## Large Bucket — Task Timeout or Memory Issues

**Symptom**: Task creation fails or times out for buckets with millions of objects.

**Cause**: `type = "prefix"` with `object = [""]` loads the entire bucket listing into the task.

**Solution**: Use `type = "list"` with a pre-generated object list file:
1. Generate the object list file (one key per line).
2. Upload it to an OBS helper bucket in the destination region.
3. Reference it in the task:

```hcl
source_object {
  data_source     = "AWS"
  region          = var.src_region
  bucket          = var.src_bucket
  access_key      = var.src_ak
  secret_key      = var.src_sk
  list_file_bucket = "helper-bucket"
  list_file_key    = "object-lists/batch-001.txt"
}
type = "list"
```

Split very large lists into multiple files and create a `huaweicloud_oms_migration_task_group` to manage them with shared bandwidth limits.

---

## Destination Bucket Not Empty — Overwrite Behavior

**Symptom**: Some objects are skipped in the destination; migration appears incomplete.

**Cause**: The destination bucket already had objects with the same keys. The default `SIZE_LAST_MODIFIED_COMPARISON_OVERWRITE` mode skips objects where the destination is newer or same size.

**Solution**: Choose the appropriate overwrite mode:

| Mode | Behavior |
|------|----------|
| `NO_OVERWRITE` | Never overwrite — keep all existing destination objects |
| `SIZE_LAST_MODIFIED_COMPARISON_OVERWRITE` | Overwrite only if source is newer or different size (default, idempotent) |
| `FULL_OVERWRITE` | Always overwrite — force re-copy everything |
| `CRC64_COMPARISON_OVERWRITE` | Overwrite if CRC64 differs (Aliyun/Tencent/HC only) |

For a clean re-migration: `object_overwrite_mode = "FULL_OVERWRITE"`.

---

## SMN Topic Not Found

**Symptom**: Task creation fails with an error about SMN topic URN.

**Cause**: The `topic_urn` in `smn_config` does not exist or is in a different region/project.

**Solution**: Verify the topic exists:
```bash
hcloud SMN ListTopicAttributes --cli-region=<region> --topic_urn=<urn>
```

Ensure the topic is in the same region as the OMS task. The URN format is:
`urn:smn:<region>:<project-id>:<topic-name>`

---

## Terraform Destroy Removes Migrated Objects

**Symptom**: Running `terraform destroy` deletes the OBS bucket and all migrated objects.

**Cause**: The `huaweicloud_obs_bucket` is managed by the Terraform config, so destroy removes it.

**Solution**: To keep the bucket and objects, destroy only the OMS task:
```bash
terraform destroy -target=huaweicloud_oms_migration_task.migration -var=...
```

Or set `force_destroy = false` (default) on the bucket — Terraform will refuse to destroy a non-empty bucket, protecting your data. Only set `force_destroy = true` if you explicitly want to delete everything.
