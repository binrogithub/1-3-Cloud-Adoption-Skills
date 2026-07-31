# AWS S3 to Huawei OBS migration via OMS Terraform

**Session ID:** ses_0fb7d1f3fffepONGKZjUDaXqYW
**Created:** 6/26/2026, 10:18:33 AM
**Updated:** 6/26/2026, 10:30:31 AM

---

## User

Lets do a migration from AWS S3 to Huawei Cloud OBS, using OMS migration tool from Huawei Cloud, please check the resources of S3 in AWS and check Terraform MCP about OMS so we can do the migration using terraform

---

## Assistant (Plan · GLM-5.2 · 19.0s)

I'll research both sides in parallel: AWS S3 resources and the HuaweiCloud Terraform OMS provider. Let me start.

**Tool: aws-mcp_aws___call_aws**

**Input:**
```json
{
  "cli_command": "aws s3api list-buckets --output json"
}
```

**Output:**
```
{"Buckets":[{"Name":"demo-bucket-17b5e8a2","CreationDate":"2026-06-16T16:31:19+00:00","BucketArn":"arn:aws:s3:::demo-bucket-17b5e8a2"}],"Owner":{"ID":"1226e6e652fb172801a1e5f390088ee223f5d4926dcde86098f8a31ede797aa6"}}
```

**Tool: terraform_search_providers**

**Input:**
```json
{
  "provider_name": "huaweicloud",
  "provider_namespace": "huaweicloud",
  "service_slug": "oms",
  "provider_document_type": "resources"
}
```

**Output:**
```
Available Documentation (top matches) for resources in Terraform provider huaweicloud/huaweicloud version: 1.93.0

Each result includes:
- providerDocID: tfprovider-compatible identifier
- Title: Service or resource name
- Category: Type of document
- Description: Brief summary of the document
For best results, select libraries based on the service_slug match and category of information requested.

---

- providerDocID: 12526721
- Title: oms_migration_sync_task
- Category: resources
- Description: 
---
- providerDocID: 12526722
- Title: oms_migration_task
- Category: resources
- Description: 
---
- providerDocID: 12526723
- Title: oms_migration_task_group
- Category: resources
- Description: 
---
- providerDocID: 12526724
- Title: oms_sync_event
- Category: resources
- Description: Manages an OMS synchronization event resource within HuaweiCloud.
---

```

**Tool: bash**

**Input:**
```json
{
  "command": "pwd && ls -la"
}
```

**Output:**
```
/home/ubuntu/code/demo-migration/huaweicloud/oms
total 12
drwxr-xr-x 2 ubuntu ubuntu 4096 Jun 26 10:14 .
drwxr-xr-x 5 ubuntu ubuntu 4096 Jun 26 10:07 ..
-rw-r--r-- 1 ubuntu ubuntu   68 Jun 26 10:14 awscredentials.csv

```

---

## Assistant (Plan · GLM-5.2 · 16.0s)

Found 1 S3 bucket (`demo-bucket-17b5e8a2`) and the HuaweiCloud OMS Terraform resources. Let me gather details on both sides.

**Tool: read**

**Input:**
```json
{
  "filePath": "/home/ubuntu/code/demo-migration/huaweicloud/oms/awscredentials.csv"
}
```

**Output:**
```
<path>/home/ubuntu/code/demo-migration/huaweicloud/oms/awscredentials.csv</path>
<type>file</type>
<content>
1: AK,SK
2: YOUR_AWS_ACCESS_KEY_ID,YOUR_AWS_SECRET_ACCESS_KEY

(End of file - total 2 lines)
</content>
```

**Tool: aws-mcp_aws___call_aws**

**Input:**
```json
{
  "cli_command": "aws s3api get-bucket-location --bucket demo-bucket-17b5e8a2"
}
```

**Output:**
```
{"LocationConstraint":"us-east-2"}
```

**Tool: aws-mcp_aws___call_aws**

**Input:**
```json
{
  "cli_command": "aws s3api list-objects-v2 --bucket demo-bucket-17b5e8a2 --output json"
}
```

**Output:**
```
{"Contents":[{"Key":"Weekly Report Week 10.docx","LastModified":"2026-06-16T21:52:45+00:00","ETag":"\"736b74ca927c47ee639b207bea46f388\"","ChecksumAlgorithm":["CRC64NVME"],"ChecksumType":"FULL_OBJECT","Size":75708,"StorageClass":"STANDARD"},{"Key":"Weekly Report Week 11.docx","LastModified":"2026-06-16T21:52:45+00:00","ETag":"\"d44eb88392983cd162a2f2b95fa85277\"","ChecksumAlgorithm":["CRC64NVME"],"ChecksumType":"FULL_OBJECT","Size":76105,"StorageClass":"STANDARD"},{"Key":"Weekly Report Week 12.docx","LastModified":"2026-06-16T21:52:46+00:00","ETag":"\"6411eb6980256febb9ab743d5fe77da6\"","ChecksumAlgorithm":["CRC64NVME"],"ChecksumType":"FULL_OBJECT","Size":76264,"StorageClass":"STANDARD"},{"Key":"Weekly Report Week 13.docx","LastModified":"2026-06-16T21:52:46+00:00","ETag":"\"e17a1a5539738d723da25e230eadb71c\"","ChecksumAlgorithm":["CRC64NVME"],"ChecksumType":"FULL_OBJECT","Size":76369,"StorageClass":"STANDARD"},{"Key":"Weekly Report Week 14.docx","LastModified":"2026-06-16T21:52:46+00:00","ETag":"\"825e1b2eba3d4e0f118c7cf1e3039e83\"","ChecksumAlgorithm":["CRC64NVME"],"ChecksumType":"FULL_OBJECT","Size":76390,"StorageClass":"STANDARD"},{"Key":"Weekly Report Week 15.docx","LastModified":"2026-06-16T21:52:47+00:00","ETag":"\"f40663522b5c4a6c9a280a49b0fe5899\"","ChecksumAlgorithm":["CRC64NVME"],"ChecksumType":"FULL_OBJECT","Size":75349,"StorageClass":"STANDARD"},{"Key":"Weekly Report Week 16.docx","LastModified":"2026-06-16T21:52:47+00:00","ETag":"\"7114df43b0499819d0ef8039e8aee69b\"","ChecksumAlgorithm":["CRC64NVME"],"ChecksumType":"FULL_OBJECT","Size":75913,"StorageClass":"STANDARD"},{"Key":"Weekly Report Week 17.docx","LastModified":"2026-06-16T21:52:47+00:00","ETag":"\"de91c5e2123b3f473e3f2839bb437381\"","ChecksumAlgorithm":["CRC64NVME"],"ChecksumType":"FULL_OBJECT","Size":76250,"StorageClass":"STANDARD"},{"Key":"Weekly Report Week 18.docx","LastModified":"2026-06-16T21:52:48+00:00","ETag":"\"f179ac26c71d18c2f52d58b1020e92f6\"","ChecksumAlgorithm":["CRC64NVME"],"ChecksumType":"FULL_OBJECT","Size":76025,"StorageClass":"STANDARD"},{"Key":"Weekly Report Week 19.docx","LastModified":"2026-06-16T21:52:48+00:00","ETag":"\"034e8c5fd362b4ad3dfec978f777df85\"","ChecksumAlgorithm":["CRC64NVME"],"ChecksumType":"FULL_OBJECT","Size":75977,"StorageClass":"STANDARD"},{"Key":"Weekly Report Week 20.docx","LastModified":"2026-06-16T21:52:48+00:00","ETag":"\"cba75a0121186cf290fc70b06cba0be1\"","ChecksumAlgorithm":["CRC64NVME"],"ChecksumType":"FULL_OBJECT","Size":75753,"StorageClass":"STANDARD"},{"Key":"Weekly Report Week 21.docx","LastModified":"2026-06-16T21:52:48+00:00","ETag":"\"a6dcfa4a302cd40d43610b2cf341cef5\"","ChecksumAlgorithm":["CRC64NVME"],"ChecksumType":"FULL_OBJECT","Size":75861,"StorageClass":"STANDARD"},{"Key":"Weekly Report Week 22.docx","LastModified":"2026-06-16T21:52:49+00:00","ETag":"\"18c9277d101d67ef08e84a883f90f7d1\"","ChecksumAlgorithm":["CRC64NVME"],"ChecksumType":"FULL_OBJECT","Size":76352,"StorageClass":"STANDARD"},{"Key":"Weekly Report Week 23.docx","LastModified":"2026-06-16T21:52:49+00:00","ETag":"\"d006b91cd4997fb7207671ee5fd00b59\"","ChecksumAlgorithm":["CRC64NVME"],"ChecksumType":"FULL_OBJECT","Size":75702,"StorageClass":"STANDARD"},{"Key":"Weekly Report Week 24.docx","LastModified":"2026-06-16T21:52:49+00:00","ETag":"\"e4b6315e969c3beb943474a54006ed6a\"","ChecksumAlgorithm":["CRC64NVME"],"ChecksumType":"FULL_OBJECT","Size":75682,"StorageClass":"STANDARD"}],"Prefix":""}
```

**Tool: aws-mcp_aws___call_aws**

**Input:**
```json
{
  "cli_command": "aws s3api get-bucket-versioning --bucket demo-bucket-17b5e8a2"
}
```

**Output:**
```
{"Status":"Enabled"}
```

**Tool: aws-mcp_aws___call_aws**

**Input:**
```json
{
  "cli_command": "aws s3api get-bucket-encryption --bucket demo-bucket-17b5e8a2"
}
```

**Output:**
```
{"ServerSideEncryptionConfiguration":{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"},"BucketKeyEnabled":false,"BlockedEncryptionTypes":{"EncryptionType":["SSE-C"]}}]}}
```

**Tool: aws-mcp_aws___call_aws**

**Input:**
```json
{
  "cli_command": "aws s3api get-bucket-tagging --bucket demo-bucket-17b5e8a2"
}
```

**Output:**
```
{"TagSet":[{"Key":"Name","Value":"demo-bucket"}]}
```

**Tool: terraform_get_provider_details**

**Input:**
```json
{
  "provider_doc_id": "12526722"
}
```

**Output:**
```
---
subcategory: "Object Storage Migration Service (OMS)"
layout: "huaweicloud"
page_title: "HuaweiCloud: huaweicloud_oms_migration_task"
description: ""
---

# huaweicloud_oms_migration_task

Manages an OMS migration task resource within HuaweiCloud.

## Example Usage

```hcl
variable "source_region" {}
variable "source_bucket" {}
variable "source_access_key" {}
variable "source_secret_key" {}
variable "dest_region" {}
variable "dest_bucket" {}
variable "dest_access_key" {}
variable "dest_secret_key" {}
variable "topic_urn" {}

resource "huaweicloud_oms_migration_task" "test" {
  source_object {
    data_source = "Aliyun"
    region      = var.source_region
    bucket      = var.source_bucket
    access_key  = var.source_access_key
    secret_key  = var.source_secret_key
    object      = [""]
  }

  destination_object {
    region     = var.dest_region
    bucket     = var.dest_bucket
    access_key = var.dest_access_key
    secret_key = var.dest_secret_key
  }

  type        = "object"
  description = "test task"

  bandwidth_policy {
    max_bandwidth = 2
    start         = "15:00"
    end           = "16:00"
  }

  smn_config {
    topic_urn          = var.topic_urn
    trigger_conditions = ["FAILURE", "SUCCESS"]
  }
}
```

## Argument Reference

The following arguments are supported:

* `region` - (Optional, String, ForceNew) Specifies the region in which to create the resource. If omitted, the
  provider-level region will be used. Changing this creates a new resource.

* `source_object` - (Required, List, ForceNew) Specifies the source information. The [object](#source_object_object)
  structure is documented below. Changing this creates a new resource.

* `destination_object` - (Required, List, ForceNew) Specifies the destination information. The [object](#destination_object_object)
  structure is documented below. Changing this creates a new resource.

* `type` - (Required, String, ForceNew) Specifies the task type. The value can be:
  + **list**: indicates migrating objects using an object list.
  + **url_list**: indicates migrating objects using a URL object list.
  + **object**: indicates migrating selected files or folders.
  + **prefix**: indicates migrating objects with specified prefixes.
  
  Changing this creates a new resource.

* `start_task` - (Optional, Bool) Specifies whether to start the task. Default value: **true**.

* `enable_kms` - (Optional, Bool, ForceNew) Specifies whether to enable the KMS encryption function.
  Default value: **false**. Changing this creates a new resource.

* `description` - (Optional, String, ForceNew) Specifies the description of the task.
  Changing this creates a new resource.

* `migrate_since` - (Optional, String, ForceNew) Specifies a time in format **yyyy-MM-dd HH:mm:ss**,
  e.g. **2006-01-02 15:04:05**. The system migrates only the objects that are modified after the specified time.
  No time is specified by default. Changing this creates a new resource.

* `enable_restore` - (Optional, Bool, ForceNew) Specifies whether to automatically restore the archive data. If enabled,
  archive data is automatically restored and migrated. Default value: **false**. Changing this creates a new resource.

* `enable_failed_object_recording` - (Optional, Bool, ForceNew) Specifies whether to record failed objects. If this
  function is enabled, information about objects that fail to be migrated will be stored in the destination bucket.
  Default value: **true**. Changing this creates a new resource.

* `bandwidth_policy` - (Optional, List) Specifies the traffic limit rules. Each element in the array
  corresponds to the maximum bandwidth of a time segment. A maximum of 5 time segments are allowed, and the time
  segments must not overlap. The [object](#bandwidth_policy_object) structure is  documented below.

* `source_cdn` - (Optional, List, ForceNew) Specifies the CDN information. If this parameter is contained,
  using CDN to download source data is supported, the source objects to be migrated are obtained from the CDN domain
  name during migration. The [object](#source_cdn_object) structure is documented below.
  Changing this creates a new resource.

* `smn_config` - (Optional, List, ForceNew) Specifies the SMN message sending configuration.
  The [object](#smn_config_object) structure is  documented below. Changing this creates a new resource.

* `object_overwrite_mode` - (Optional, String, ForceNew) Specifies whether to skip a source object or allow the source
  object to overwrite its paired destination object. Value options are as follows:

  + **NO_OVERWRITE**: indicates the system never allows override. The system always skips source objects and keeps
  their paired destination objects.

  + **SIZE_LAST_MODIFIED_COMPARISON_OVERWRITE**: indicates the system allows override based on the results of size or
  modification time checks. If a source object is not as large as or was last modified more recently than its paired
  destination object, the source object will overwrite the destination object. Otherwise, the source object will be
  skipped.

  + **CRC64_COMPARISON_OVERWRITE**: indicates the system allows override if the source and destination objects have
  different CRC64 checksums. This option is only available for migration on Huawei Cloud or from Alibaba Cloud or
  Tencent Cloud. If a source object has a CRC64 checksum different from the paired destination object, the source
  object will overwrite the destination object. Otherwise, the source object will be skipped.
  If any of them doesn't have a CRC64 checksum, their sizes and last modification times are checked.

  + **FULL_OVERWRITE**: indicates the system always allows override. The system always allows source objects to
  overwrite their paired destination objects.

  The default value is **SIZE_LAST_MODIFIED_COMPARISON_OVERWRITE**. Changing this creates a new resource.

* `consistency_check` - (Optional, String, ForceNew) Specifies the consistency check method, which is used to check
  whether objects are consistent before and after migration. All check methods take effect for only objects that are
  in the same encryption status in the source and destination buckets. The check method and results will be recorded
  in the object list. Value options are as follows:

  + **size_last_modified**: the system checks object consistency with object size and last modification time.
  If a source object is as large as but was last modified earlier than its paired destination object, the system
  considers the source object does not need to be migrated or has been already migrated successfully.

  + **crc64**: this option is only available for migration on Huawei Cloud or from Alibaba Cloud or Tencent Cloud. If
  a source object and its paired destination object have CRC64 checksums, the checksums are checked. Otherwise, their
  sizes and last modification times are checked.

  + **no_check**: this option is only available for migration of HTTP/HTTPS data. This option takes effect for source
  objects whose sizes cannot be obtained using the content-length field in the standard HTTP protocol. These source
  objects will overwrite their paired destination objects directly.
  If the size of a source object can be obtained, its size and last modification time will be checked.

  The default value is **size_last_modified**. Changing this creates a new resource.

* `enable_requester_pays` - (Optional, Bool, ForceNew) Specifies whether to let the requester make payment.
  After enabled, the requester pays the request and data transmission fees.
  Default value: **false**. Changing this creates a new resource.

* `enable_metadata_migration` - (Optional, Bool, ForceNew) Specifies whether metadata migration is enabled. Even if this
  function is disabled, the ContentType metadata will still be migrated to ensure a successful migration.
  Default value: **false**. Changing this creates a new resource.

* `task_priority` - (Optional, String, ForceNew) Specifies the task priority.
  The value can be **HIGH**, **MEDIUM**, or **LOW**. Changing this creates a new resource.

* `dst_storage_policy` - (Optional, String, ForceNew) Specifies the destination storage class.
  This parameter is required only when the destination is Huawei Cloud OBS. The default value is STANDARD.
  + **STANDARD**: OBS Standard storage.
  + **IA**: OBS Infrequent Access storage.
  + **ARCHIVE**: OBS Archive storage
  + **DEEP_ARCHIVE**: OBS Deep Archive storage
  + **SRC_STORAGE_MAPPING**: converts the source storage class into an OBS storage class based on the predefined rules.
  Changing this creates a new resource.

<a name="source_object_object"></a>
The `source_object` block supports:

* `region` - (Optional, String, ForceNew) Specifies the region where the source bucket is located. `region` is mandatory
  when `type` is not **url_list**. Changing this creates a new resource.

* `bucket` - (Optional, String, ForceNew) Specifies the name of the source bucket. `bucket` is mandatory when `type`
  is not **url_list**. Changing this creates a new resource.

* `access_key` - (Optional, String, ForceNew) Specifies the access key for accessing the source bucket. This parameter
  is mandatory when `type` is not **url_list**. Changing this creates a new resource.

* `secret_key` - (Optional, String, ForceNew) Specifies the secret key for accessing the destination bucket. This
  parameter is mandatory when `type` is not **url_list**. Changing this creates a new resource.

* `security_token` - (Optional, String, ForceNew) Specifies the temporary token for accessing the source bucket.
  Changing this creates a new resource.

* `object` - (Optional, List, ForceNew) Specifies the list of object keys.
  + If `type` is set to **object**, this parameter specifies the names of the objects to be migrated. The strings
  ending with a slash (/) indicate the folders to be migrated, and the strings not ending with a slash (/) indicate the
  files to be migrated.
  + If `type` is set to **prefix**, this parameter indicates the name prefixes of the objects to be migrated.
  Set this parameter to [""] to migrate the entire bucket
  
  Changing this creates a new resource.

* `data_source` - (Optional, String, ForceNew) Specifies the source cloud service provider. If `type` is
  **url_list**,set this parameter to **URLSource**. The value can be **AWS**, **Azure**, **Aliyun**, **Tencent**,
  **HuaweiCloud**, **QingCloud**, **KingsoftCloud**, **Baidu**, **Qiniu**, **URLSource** and **UCloud**.
  The default value is **Aliyun**. Changing this creates a new resource.

* `app_id` - (Optional, String, ForceNew) Specifies the APP ID. This parameter is mandatory when `data_source` is  
  **Tencent**. Changing this creates a new resource.

* `list_file_bucket` - (Optional, String, ForceNew) Specifies the name of the OBS bucket for storing the object list files.
  `list_file_bucket` is mandatory when `type` is set to **list** or **url_list**. Changing this creates a new resource.
  
  -> Ensure that the OBS bucket is in the same region as the destination bucket, or the task will fail to be created.

* `list_file_key` - (Optional, String, ForceNew) Specifies the object name of the list file or URL list file.
  `list_file_key` is mandatory when `type` is set to **list** or **url_list**. Changing this creates a new resource.

* `list_file_num` - (Optional, String, ForceNew) Specifies the number of stored object list files.
  Changing this creates a new resource.

* `json_auth_file` - (Optional, String, ForceNew) Specifies the file used for Google Cloud Storage authentication.
  Changing this creates a new resource.

<a name="destination_object_object"></a>
The `destination_object` block supports:

* `region` - (Required, String, ForceNew) Specifies the region where the destination bucket is located.
  Changing this creates a new resource.

* `bucket` - (Required, String, ForceNew) Specifies the name of the destination bucket.
  Changing this creates a new resource.

* `access_key` - (Required, String, ForceNew) Specifies the access key for accessing the destination bucket.
  Changing this creates a new resource.

* `secret_key` - (Required, String, ForceNew) Specifies the secret key for accessing the destination bucket.
  Changing this creates a new resource.

* `security_token` - (Optional, String, ForceNew) Specifies the temporary token for accessing the destination bucket.
  Changing this creates a new resource.

* `save_prefix` - (Optional, String, ForceNew) Specifies the path prefix in the destination bucket. The prefix is added
  before the object key to form a new key. Changing this creates a new resource.

<a name="bandwidth_policy_object"></a>
The `bandwidth_policy` block supports:

* `max_bandwidth` - (Required, Int) Specifies the maximum traffic bandwidth allowed in the specified time
  segment. The value ranges from `1` to `200`. The unit is MB/s.

* `start` - (Required, String) Specifies the start time of the traffic limit rule. The format is **hh:mm**,
  e.g. **12:03**.

* `end` - (Required, String) Specifies the end time of the traffic limit rule. The format is **hh:mm**,
  e.g. **12:03**.

<a name="source_cdn_object"></a>
The `source_cdn` block supports:

* `domain` - (Required, String, ForceNew) Specifies the domain name from which to obtain objects to be migrated.
  Changing this creates a new resource.

* `protocol` - (Required, String, ForceNew) Specifies the protocol type. Valid values are **HTTP** and **HTTPS**.
  Changing this creates a new resource.

* `authentication_type` - (Optional, String, ForceNew) Specifies the authentication type. Valid values are **NONE**,
  **QINIU_PRIVATE_AUTHENTICATION**, **ALIYUN_OSS_A**, **ALIYUN_OSS_B**, **ALIYUN_OSS_C**,
  **KSYUN_PRIVATE_AUTHENTICATION**, **TENCENT_COS_A**, **TENCENT_COS_B**, **TENCENT_COS_C**,
  **TENCENT_COS_D**. Default value: **None**. Changing this creates a new resource.

* `authentication_key` - (Optional, String, ForceNew) Specifies the CDN authentication key.
  Changing this creates a new resource.

<a name="smn_config_object"></a>
The `smn_config` block supports:

* `topic_urn` - (Required, String, ForceNew) Specifies the SMN message topic URN bound to a migration task.
  Changing this creates a new resource.

* `trigger_conditions` - (Required, List, ForceNew) Specifies the trigger conditions of sending messages using SMN.
  The value can be:
  + **FAILURE**: indicates that an SMN message will be sent after the migration task fails.
  + **SUCCESS**: indicates that an SMN message will be sent after the migration task succeeds.

  Changing this creates a new resource.

* `language` - (Optional, String, ForceNew) Specifies the SMN message language. The value can be **zh-cn** or
  **en-us**. Default value: **en-us**. Changing this creates a new resource.

* `message_template_name` - (Optional, String, ForceNew) Specifies the message template name.
  If this parameter is specified, SMN messages are sent using the specified template.
  Changing this creates a new resource.

## Attribute Reference

In addition to all arguments above, the following attributes are exported:

* `id` - The ID of the migration task.

* `name` - The name of the migration task.

* `status` - The status the migration task. The value can be:
  + **1**: Waiting to migrate.
  + **2**: Migrating.
  + **3**: Migration paused.
  + **4**: Migration failed.
  + **5**: Migration succeeded.

## Timeouts

This resource provides the following timeouts configuration options:

* `create` - Default is 10 minutes.

```

**Tool: terraform_get_provider_details**

**Input:**
```json
{
  "provider_doc_id": "12526721"
}
```

**Output:**
```
---
subcategory: "Object Storage Migration Service (OMS)"
layout: "huaweicloud"
page_title: "HuaweiCloud: huaweicloud_oms_migration_sync_task"
description: ""
---

# huaweicloud_oms_migration_sync_task

Manages an OMS migration synchronization task resource within HuaweiCloud.

## Example Usage

```hcl
variable "source_region" {}
variable "source_bucket" {}
variable "source_access_key" {}
variable "source_secret_key" {}
variable "dest_region" {}
variable "dest_bucket" {}
variable "dest_access_key" {}
variable "dest_secret_key" {}

resource "huaweicloud_oms_migration_sync_task" "test" {
  region = var.dest_region

  src_cloud_type = "HuaweiCloud"
  src_region     = var.source_region
  src_bucket     = var.source_bucket
  src_ak         = var.source_access_key
  src_sk         = var.source_secret_key
  dst_bucket     = var.dest_bucket
  dst_ak         = var.dest_access_key
  dst_sk         = var.dest_secret_key
}
```

## Argument Reference

The following arguments are supported:

* `region` - (Optional, String, ForceNew) Specifies the region in which to create the resource. Which is also the region
  for the destination bucket. If omitted, the provider-level region will be used.
  Changing this creates a new resource.

* `src_region` - (Required, String, ForceNew) Specifies the region where the source bucket is located.
  Changing this creates a new resource.

* `src_bucket` - (Required, String, ForceNew) Specifies the name of the source bucket.
  Changing this creates a new resource.

* `src_ak` - (Required, String, ForceNew) Specifies the access key for accessing the source bucket.
  Changing this creates a new resource.

* `src_sk` - (Required, String, ForceNew) Specifies the secret key for accessing the source bucket.
  Changing this creates a new resource.

* `dst_bucket` - (Required, String, ForceNew) Specifies the name of the destination bucket.
  Changing this creates a new resource.

* `dst_ak` - (Required, String, ForceNew) Specifies the access key for accessing the destination bucket.
  Changing this creates a new resource.

* `dst_sk` - (Required, String, ForceNew) Specifies the secret key for accessing the destination bucket.
  Changing this creates a new resource.

* `src_cloud_type` - (Optional, String, ForceNew) Specifies the source cloud service provider. Value options:
  **AWS**, **Azure**, **Aliyun**, **Tencent**, **HuaweiCloud**, **QingCloud**, **KingsoftCloud**, **Baidu**,
  **Qiniu**, **URLSource** and **UCloud**. Default value: **Aliyun**. Changing this creates a new resource.

* `app_id` - (Optional, String, ForceNew) Specifies the APP ID. This parameter is mandatory when `src_cloud_type` is
  **Tencent**. Changing this creates a new resource.

* `consistency_check` - (Optional, String, ForceNew) Specifies the consistency check method, which is used to check
  whether objects are consistent before and after migration. All check methods take effect for only objects that are
  in the same encryption status in the source and destination buckets. The check method and results will be recorded
  in the object list. Value options:

  + **size_last_modified**: the system checks object consistency with object size and last modification time.
    If a source object is as large as but was last modified earlier than its paired destination object, the system
    considers the source object does not need to be migrated or has been already migrated successfully.

  + **crc64**: this option is only available for migration on Huawei Cloud or from Alibaba Cloud or Tencent Cloud. If
    a source object and its paired destination object have CRC64 checksums, the checksums are checked. Otherwise, their
    sizes and last modification times are checked.

  + **no_check**: this option is only available for migration of HTTP/HTTPS data. This option takes effect for source
    objects whose sizes cannot be obtained using the content-length field in the standard HTTP protocol. These source
    objects will overwrite their paired destination objects directly.
    If the size of a source object can be obtained, its size and last modification time will be checked.

  The default value is **size_last_modified**. Changing this creates a new resource.

* `description` - (Optional, String, ForceNew) Specifies the description of the synchronization task.
  Changing this creates a new resource.

* `enable_kms` - (Optional, Bool, ForceNew) Specifies whether to enable the KMS encryption function.
  Default value: **false**. Changing this creates a new resource.

* `enable_metadata_migration` - (Optional, Bool, ForceNew) Specifies whether metadata migration is enabled.
  Default value: **false**. Even if disabled, the ContentType metadata will still be migrated
  to ensure a successful migration. Changing this creates a new resource.

* `enable_restore` - (Optional, Bool, ForceNew) Specifies whether to automatically restore the archive data. If enabled,
  archive data is automatically restored and migrated. Default value: **false**. Changing this creates a new resource.

* `source_cdn` - (Optional, List, ForceNew) Specifies the CDN information. If this parameter is contained,
  using CDN to download source data is supported, the source objects to be migrated are obtained from the CDN domain
  name during migration. Changing this creates a new resource.
  The [source_cdn](#block--source_cdn) structure is documented below.

* `action` - (Optional, String) Specifies the action for migration synchronization task. Value options:

  + **start**: Start a migration synchronization task.
  + **stop**:  Pause a migration synchronization task.

<a name="block--source_cdn"></a>
The `source_cdn` block supports:

* `domain` - (Required, String, ForceNew) Specifies the domain name from which to obtain objects to be migrated.
  Changing this creates a new resource.

* `protocol` - (Required, String, ForceNew) Specifies the protocol type. Value options: **http** and **https**.
  Changing this creates a new resource.

* `authentication_type` - (Optional, String, ForceNew) Specifies the authentication type. Value options:

  + **NONE**
  + **QINIU_PRIVATE_AUTHENTICATION**
  + **ALIYUN_OSS_A**
  + **ALIYUN_OSS_B**
  + **ALIYUN_OSS_C**
  + **KSYUN_PRIVATE_AUTHENTICATION**
  + **TENCENT_COS_A**
  + **TENCENT_COS_B**
  + **TENCENT_COS_C**
  + **TENCENT_COS_D**

  Default value: **NONE**. Changing this creates a new resource.

* `authentication_key` - (Optional, String, ForceNew) Specifies the CDN authentication key.
  Changing this creates a new resource.

## Attribute Reference

In addition to all arguments above, the following attributes are exported:

* `id` -  The resource ID.

* `created_at` - Indicates the time when the migration synchronization task was created.

* `dst_storage_policy` - Indicates the destination storage class. The value can be:

  + **STANDARD**
  + **IA**
  + **ARCHIVE**
  + **DEEP_ARCHIVE**
  + **SRC_STORAGE_MAPPING**

* `last_start_at` - Indicates the last time when the migration synchronization task started.

* `monthly_acceptance_request` - Indicates the number of objects requested to be synchronized in the current month.

* `monthly_failure_object` - Indicates the number of objects that failed to be synchronized in the current month.

* `monthly_size` - Indicates the total size of synchronized objects in the current month, in bytes.

* `monthly_skip_object` - Indicates the number of objects that were ignored in the current month.

* `monthly_success_object` - Indicates the number of objects that were successfully synchronized in the current month.

* `object_overwrite_mode` - Indicates the type of the source object to overwrite its paired destination object.
  The value can be:

  + **NO_OVERWRITE**: Indicates the system never allows override. The system always skips source objects and keeps
    their paired destination objects.

  + **SIZE_LAST_MODIFIED_COMPARISON_OVERWRITE**: Indicates the system allows override based on the results of size or
    modification time checks. If a source object is not as large as or was last modified more recently than its paired
    destination object, the source object will overwrite the destination object. Otherwise, the source object will be
    skipped.

  + **CRC64_COMPARISON_OVERWRITE**: Indicates the system allows override if the source and destination objects have
    different CRC64 checksums. This option is only available for migration on Huawei Cloud or from Alibaba Cloud or
    Tencent Cloud. If a source object has a CRC64 checksum different from the paired destination object, the source
    object will overwrite the destination object. Otherwise, the source object will be skipped.
    If any of them doesn't have a CRC64 checksum, their sizes and last modification times are checked.

  + **FULL_OVERWRITE**: Indicates the system always allows override. The system always allows source objects to
    overwrite their paired destination objects.

* `status` - Indicates the status of the migration synchronization task. The value can be:

  + **SYNCHRONIZING**:synchronizing.
  + **STOPPED**:stopped.

```

**Tool: terraform_get_provider_details**

**Input:**
```json
{
  "provider_doc_id": "12526723"
}
```

**Output:**
```
---
subcategory: "Object Storage Migration Service (OMS)"
layout: "huaweicloud"
page_title: "HuaweiCloud: huaweicloud_oms_migration_task_group"
description: ""
---

# huaweicloud_oms_migration_task_group

Manages an OMS migration task group resource within HuaweiCloud.

## Example Usage

### OMS Migration Task Group with PREFIX

```hcl
variable "source_region" {}
variable "source_bucket" {}
variable "source_access_key" {}
variable "source_secret_key" {}
variable "dest_region" {}
variable "dest_bucket" {}
variable "dest_access_key" {}
variable "dest_secret_key" {}

resource "huaweicloud_oms_migration_task_group" "test" {
  source_object {
    data_source = "Aliyun"
    region      = var.source_region
    bucket      = var.source_bucket
    access_key  = var.source_access_key
    secret_key  = var.source_secret_key
    object      = [""]
  }

  destination_object {
    region     = var.dest_region
    bucket     = var.dest_bucket
    access_key = var.dest_access_key
    secret_key = var.dest_secret_key
  }

  type                           = "PREFIX"
  enable_kms                     = true
  description                    = "test task group"
  migrate_since                  = "2023-01-02 15:04:05"
  object_overwrite_mode          = "CRC64_COMPARISON_OVERWRITE"
  consistency_check              = "crc64"
  enable_requester_pays          = true
  enable_failed_object_recording = true

  bandwidth_policy {
    max_bandwidth = 1
    start         = "15:00"
    end           = "16:00"
  }

  bandwidth_policy {
    max_bandwidth = 2
    start         = "16:00"
    end           = "17:00"
  }
}
```

### OMS Migration Task Group with LIST

```hcl
variable "source_region" {}
variable "source_bucket" {}
variable "source_access_key" {}
variable "source_secret_key" {}
variable "dest_region" {}
variable "dest_bucket" {}
variable "dest_access_key" {}
variable "dest_secret_key" {}
variable "list_file_bucket" {}
variable "list_file_key" {}

resource "huaweicloud_oms_migration_task_group" "test" {
  source_object {
    data_source      = "HuaweiCloud"
    region           = var.source_region
    bucket           = var.source_bucket
    access_key       = var.source_access_key
    secret_key       = var.source_secret_key
    list_file_bucket = var.list_file_bucket
    list_file_key    = var.list_file_key
  }

  destination_object {
    region     = var.dest_region
    bucket     = var.dest_bucket
    access_key = var.dest_access_key
    secret_key = var.dest_secret_key
  }

  type        = "LIST"
  description = "test task group"
}
```

### OMS Migration Task Group with URL_LIST

```hcl
variable "dest_region" {}
variable "dest_bucket" {}
variable "dest_access_key" {}
variable "dest_secret_key" {}
variable "list_file_bucket" {}
variable "list_file_key" {}

resource "huaweicloud_oms_migration_task_group" "test" {
  source_object {
    data_source      = "URLSource"
    list_file_bucket = var.list_file_bucket
    list_file_key    = var.list_file_key
  }

  destination_object {
    region     = var.dest_region
    bucket     = var.dest_bucket
    access_key = var.dest_access_key
    secret_key = var.dest_secret_key
  }

  type        = "URL_LIST"
  description = "test task group"
}
```

## Argument Reference

The following arguments are supported:

* `region` - (Optional, String, ForceNew) Specifies the region in which to create the resource. If omitted, the
  provider-level region will be used. Changing this creates a new resource.

* `source_object` - (Required, List, ForceNew) Specifies the source information. The [object](#source_object_object)
  structure is documented below. Changing this creates a new resource.

* `destination_object` - (Required, List, ForceNew) Specifies the destination information.
  The [object](#destination_object_object) structure is documented below. Changing this creates a new resource.

* `type` - (Required, String, ForceNew) Specifies the task group type. The value can be:
  + **LIST**: indicates that the system will migrate the objects specified in the object list.
  + **URL_LIST**: indicates that the system will migrate the objects specified in the URL list.
  + **PREFIX**: indicates that the system will migrate the objects with a specific prefix.

  The default value is **PREFIX**. Changing this creates a new resource.

* `enable_kms` - (Optional, Bool, ForceNew) Specifies whether to enable the KMS encryption function.
  Default value: **false**. Changing this creates a new resource.

* `description` - (Optional, String, ForceNew) Specifies the description of the task group. The message cannot
  exceed 255 characters. The following special characters are not allowed: ^<>&"'.
  Changing this creates a new resource.

* `migrate_since` - (Optional, String, ForceNew) Specifies a time in format **yyyy-MM-dd HH:mm:ss**,
  e.g. **2006-01-02 15:04:05**. The system migrates only the objects that are modified after the specified time.
  No time is specified by default. Changing this creates a new resource.

* `object_overwrite_mode` - (Optional, String, ForceNew) Specifies whether to skip a source object or allow the source
  object to overwrite its paired destination object. Value options are as follows:

  + **NO_OVERWRITE**: indicates the system never allows override. The system always skips source objects and keeps
  their paired destination objects.

  + **SIZE_LAST_MODIFIED_COMPARISON_OVERWRITE**: indicates the system allows override based on the results of size or
  modification time checks. If a source object is not as large as or was last modified more recently than its paired
  destination object, the source object will overwrite the destination object. Otherwise, the source object will be
  skipped.

  + **CRC64_COMPARISON_OVERWRITE**: indicates the system allows override if the source and destination objects have
  different CRC64 checksums. This option is only available for migration on Huawei Cloud or from Alibaba Cloud or
  Tencent Cloud. If a source object has a CRC64 checksum different from the paired destination object, the source
  object will overwrite the destination object. Otherwise, the source object will be skipped.
  If any of them doesn't have a CRC64 checksum, their sizes and last modification times are checked.

  + **FULL_OVERWRITE**: indicates the system always allows override. The system always allows source objects to
  overwrite their paired destination objects.

  The default value is **SIZE_LAST_MODIFIED_COMPARISON_OVERWRITE**. Changing this creates a new resource.

* `consistency_check` - (Optional, String, ForceNew) Specifies the consistency check method, which is used to check
  whether objects are consistent before and after migration. All check methods take effect for only objects that are
  in the same encryption status in the source and destination buckets. The check method and results will be recorded
  in the object list. Value options are as follows:

  + **size_last_modified**: the system checks object consistency with object size and last modification time.
  If a source object is as large as but was last modified earlier than its paired destination object, the system
  considers the source object does not need to be migrated or has been already migrated successfully.

  + **crc64**: this option is only available for migration on Huawei Cloud or from Alibaba Cloud or Tencent Cloud. If
  a source object and its paired destination object have CRC64 checksums, the checksums are checked. Otherwise, their
  sizes and last modification times are checked.

  + **no_check**: this option is only available for migration of HTTP/HTTPS data. This option takes effect for source
  objects whose sizes cannot be obtained using the content-length field in the standard HTTP protocol. These source
  objects will overwrite their paired destination objects directly.
  If the size of a source object can be obtained, its size and last modification time will be checked.

  The default value is **size_last_modified**. Changing this creates a new resource.

* `enable_requester_pays` - (Optional, Bool, ForceNew) Specifies whether to let the requester make payment.
  After enabled, the requester pays the request and data transmission fees.
  Default value: **false**. Changing this creates a new resource.

* `action` - (Optional, String) Specifies the action for migration task group. Value options are as follows:
  + **retry**: Restart a failed migration task group. This will migrate all objects in the failed tasks again.
  + **start**: Resume a paused migration task group.
  + **stop**:  Pause a migration task group when it is being monitored.

  -> **NOTE:** The usage of `action` has some limitations. Only creation failed task groups can be retried
  and only paused task groups can be started and only monitoring task groups can be stopped.

* `enable_failed_object_recording` - (Optional, Bool, ForceNew) Specifies whether to record failed objects.
  Default value: **true**. Changing this creates a new resource.

* `bandwidth_policy` - (Optional, List) Specifies the traffic limit rules. Each element in the array
  corresponds to the maximum bandwidth of a time segment. A maximum of 5 time segments are allowed, and the time
  segments must not overlap. The [object](#bandwidth_policy_object) structure is documented below.

* `source_cdn` - (Optional, List, ForceNew) Specifies the CDN information. If this parameter is contained,
  using CDN to download source data is supported, the source objects to be migrated are obtained from the CDN domain
  name during migration. The [object](#source_cdn_object) structure is documented below.
  Changing this creates a new resource.

* `enable_metadata_migration` - (Optional, Bool, ForceNew) Specifies whether metadata migration is enabled. Even if this
  function is disabled, the ContentType metadata will still be migrated to ensure a successful migration.
  Default value: **false**. Changing this creates a new resource.

* `dst_storage_policy` - (Optional, String, ForceNew) Specifies the destination storage class.
  This parameter is required only when the destination is Huawei Cloud OBS. The default value is STANDARD.
  + **STANDARD**: OBS Standard storage.
  + **IA**: OBS Infrequent Access storage.
  + **ARCHIVE**: OBS Archive storage
  + **DEEP_ARCHIVE**: OBS Deep Archive storage
  + **SRC_STORAGE_MAPPING**: converts the source storage class into an OBS storage class based on the predefined rules.
  Changing this creates a new resource.

<a name="source_object_object"></a>
The `source_object` block supports:

* `region` - (Optional, String, ForceNew) Specifies the region where the source bucket is located. `region` is
  mandatory when `type` is not **URL_LIST**. Changing this creates a new resource.

* `bucket` - (Optional, String, ForceNew) Specifies the name of the source bucket. `bucket` is mandatory when `type`
  is not **URL_LIST**. Changing this creates a new resource.

* `access_key` - (Optional, String, ForceNew) Specifies the access key for accessing the source bucket. This parameter
  is mandatory when `type` is not **URL_LIST**. Changing this creates a new resource.

* `secret_key` - (Optional, String, ForceNew) Specifies the secret key for accessing the source bucket. This
  parameter is mandatory when `type` is not **URL_LIST**. Changing this creates a new resource.

* `object` - (Optional, List, ForceNew) Specifies the name prefixes of objects to be migrated if `type` is set to
  **PREFIX**. If you want to migrate the entire bucket, set this parameter to [""].
  Changing this creates a new resource.

* `data_source` - (Optional, String, ForceNew) Specifies the source cloud service provider. If `type` is
  **URL_LIST**,set this parameter to **URLSource**. The value can be **AWS**, **Azure**, **Aliyun**, **Tencent**,
  **HuaweiCloud**, **QingCloud**, **KingsoftCloud**, **Baidu**, **Qiniu**, **URLSource** or **UCloud**.
  The default value is **Aliyun**. Changing this creates a new resource.

* `app_id` - (Optional, String, ForceNew) Specifies the APP ID. This parameter is mandatory when `data_source` is
  **Tencent**. Changing this creates a new resource.

* `list_file_bucket` - (Optional, String, ForceNew) Specifies the name of the OBS bucket for storing the object
  list files. `list_file_bucket` is mandatory when `type` is set to **LIST** or **URL_LIST**.
  Changing this creates a new resource.

  -> Ensure that the OBS bucket is in the same region as the destination bucket, or the task group will fail to be
  created.

* `list_file_key` - (Optional, String, ForceNew) Specifies the OBS bucket folder name of the list file or URL list file.
  `list_file_key` is mandatory when `type` is set to **LIST** or **URL_LIST**.

  + If `type` is **LIST**: You need to write the names of source objects to be migrated into an object list file
  and store the file in an OBS bucket on HUAWEI CLOUD. OMS migrates all objects specified in the object list file.

  + If `type` is **URL_LIST**: You need to write the URLs of the files to be migrated and their destination objects
  names into one or more .txt URL list files and store the files in an OBS bucket on HUAWEI CLOUD. You can store up
  to 2,000 list files in a fixed folder in the OBS bucket. Each list file cannot exceed 1 GB. OMS migrates all
  objects specified in the URL list files.

  Changing this creates a new resource.

  -> More details for the format requirements of list file. Please see
  the [User Guide](https://support.huaweicloud.com/intl/en-us/usermanual-oms/oms_01_0017.html).

<a name="destination_object_object"></a>
The `destination_object` block supports:

* `region` - (Required, String, ForceNew) Specifies the region where the destination bucket is located.
  The value must be the same as that of the service endpoint. Changing this creates a new resource.

* `bucket` - (Required, String, ForceNew) Specifies the name of the destination bucket.
  Changing this creates a new resource.

* `access_key` - (Optional, String, ForceNew) Specifies the access key for accessing the destination bucket.
  Changing this creates a new resource.

* `secret_key` - (Optional, String, ForceNew) Specifies the secret key for accessing the destination bucket.
  Changing this creates a new resource.

* `data_source` - (Optional, String, ForceNew) Specifies the destination data source. The default value is **HEC**.
  Changing this creates a new resource.

* `save_prefix` - (Optional, String, ForceNew) Specifies the path prefix in the destination bucket. The prefix is added
  before the object key to form a new key. Changing this creates a new resource.

<a name="bandwidth_policy_object"></a>
The `bandwidth_policy` block supports:

* `max_bandwidth` - (Required, Int) Specifies the maximum traffic bandwidth allowed in the specified time
  segment. The value ranges from `1` to `200`. The unit is MB/s.

* `start` - (Required, String) Specifies the start time of the traffic limit rule. The format is **hh:mm**,
  e.g. **12:03**.

* `end` - (Required, String) Specifies the end time of the traffic limit rule. The format is **hh:mm**,
  e.g. **12:03**.

<a name="source_cdn_object"></a>
The `source_cdn` block supports:

* `domain` - (Required, String, ForceNew) Specifies the domain name from which to obtain objects to be migrated.
  Changing this creates a new resource.

* `protocol` - (Required, String, ForceNew) Specifies the protocol type. Valid values are **HTTP** and **HTTPS**.
  Changing this creates a new resource.

* `authentication_type` - (Optional, String, ForceNew) Specifies the authentication type. Valid values are **NONE**,
  **QINIU_PRIVATE_AUTHENTICATION**, **ALIYUN_OSS_A**, **ALIYUN_OSS_B**, **ALIYUN_OSS_C**,
  **KSYUN_PRIVATE_AUTHENTICATION**, **TENCENT_COS_A**, **TENCENT_COS_B**, **TENCENT_COS_C**,
  **TENCENT_COS_D**. Default value: **None**. Changing this creates a new resource.

* `authentication_key` - (Optional, String, ForceNew) Specifies the CDN authentication key.
  Changing this creates a new resource.

## Attribute Reference

In addition to all arguments above, the following attributes are exported:

* `id` - The ID of the migration task group.

* `status` - The migration task group status. The value can be:
  + **0**: Waiting.
  + **1**: Executing/Creating.
  + **2**: Monitoring.
  + **3**: Paused.
  + **4**: Creation failed.
  + **5**: Migration failed.
  + **6**: Migration completed.
  + **7**: Pausing.
  + **8**: Waiting to be deleted.
  + **9**: Deleted.

* `total_time` - The total amount of time used by the migration task group, in ms.
* `total_num` - The total number of objects to be migrated in the migration task group.
* `success_num` - The number of migrated objects.
* `fail_num` - The number of failed objects.
* `total_size` - The total size of migrated objects, in bytes.
* `complete_size` - The size (in bytes) of the objects that have been migrated.

## Timeouts

This resource provides the following timeouts configuration options:

* `create` - Default is 10 minutes.
* `update` - Default is 10 minutes.
* `delete` - Default is 10 minutes.

```

---

## Assistant (Plan · GLM-5.2 · 12.8s)

I have a complete picture of the source. Let me also check the HuaweiCloud side for existing OBS buckets and the latest provider version.

**Tool: skill**

**Input:**
```json
{
  "name": "hcloud-cli"
}
```

**Output:**
```
<skill_content name="hcloud-cli">
# Skill: hcloud-cli

# Huawei Cloud CLI (KooCLI)

## Rules

1. **DISCOVER before ACT** — always query existing resources with `List`/`Show` operations before creating or modifying anything. Avoid duplicates. Reuse existing infrastructure when possible.
2. **DRYRUN before EXECUTE** — always `--dryrun` create/update/delete calls first. Show the user what will happen. Only execute after confirmation or when the user has explicitly asked to proceed.
3. **Never hardcode IDs** — use resource names to look up IDs via list operations, then reference the IDs. In Terraform output, use data blocks or resource references.
4. **Use JMESPath** — `--cli-query` to filter output and keep token usage minimal. Never dump full API responses when you only need a few fields.
5. **Use waiter** — `--cli-waiter` for async operations (ECS create, RDS create, CCE create, etc.). Never poll manually with sleep loops.
6. **Discover services dynamically** — `hcloud <Service> --help` to find operations; `hcloud <Service> <Operation> --help` to find parameters. Never guess API names or parameters.
7. **Batch independent queries** — call multiple independent list operations in parallel. Only serialize when there's a dependency (subnets need VPC ID, RDS flavors need engine).
8. **Batch questions** — ask related questions together, not one at a time.
9. **OBS is a separate tool** — `hcloud obs` is obsutil, not a standard hcloud API. It uses single-dash flags (`-flag=value`), `obs://bucket/key` URLs, its own config (`~/.obsutilconfig`), and has no JMESPath/JSON output. See [references/obs.md](references/obs.md).

## Quick Start

```bash
# Check CLI is available
hcloud version

# Verify authentication
hcloud configure test

# Discover available services
hcloud --help

# Discover operations for a service
hcloud ECS --help

# Discover parameters for an operation
hcloud ECS ListServersDetails --help

# List existing resources (the "snapshot")
hcloud VPC ListVpcs --cli-region=la-north-2 --cli-output=json --cli-query='vpcs[].{name:name,id:id,cidr:cidr}'

# Preview a create call without executing
hcloud --dryrun VPC CreateVpc --cli-region=la-north-2 --vpc.name=demo-vpc --vpc.cidr=10.0.0.0/16

# Generate a parameter skeleton for complex operations
hcloud --skeleton ECS CreateServers

# Execute with waiter for async operations
hcloud ECS CreateServers --cli-region=la-north-2 --cli-waiter='{"expr":"server.status","to":"ACTIVE","timeout":300}' ...
```

## Core Pattern

```bash
hcloud <Service> <Operation> --param1=value1 --param2=value2
```

- **Service**: cloud service name (ECS, VPC, RDS, IAM, etc.)
- **Operation**: API operation name (ListServersDetails, CreateVpc, etc.)
- **Parameters**: `--param=value` format (always `--param=value`, never `--param value`)

### Parameter naming

- Simple params: `--name=demo-vpc`
- Nested params (body objects): `--vpc.name=demo-vpc --vpc.cidr=10.0.0.0/16`
- Array params: `--nics.1.subnet_id=xxx --nics.1.vpc_id=yyy`
- JSON input for complex bodies: `--cli-jsonInput=./params.json`

## Global Options

```bash
# Preview without executing
hcloud --dryrun ECS CreateServers ...

# Generate parameter skeleton in JSON
hcloud --skeleton ECS CreateServers

# Debug mode — print full request/response
hcloud --debug ECS ListServersDetails --cli-region=la-north-2

# Region override
hcloud ECS ListServersDetails --cli-region=ap-southeast-1

# Profile override
hcloud ECS ListServersDetails --cli-profile=prod

# Output format
hcloud VPC ListVpcs --cli-output=json          # JSON (default for scripting)
hcloud VPC ListVpcs --cli-output=table         # ASCII table
hcloud VPC ListVpcs --cli-output=tsv           # Tab-separated

# JMESPath query — filter and project output
hcloud VPC ListVpcs --cli-query='vpcs[].{name:name,id:id}'

# Async polling
hcloud ECS CreateServers --cli-waiter='{"expr":"server.status","to":"ACTIVE","timeout":300}'

# Row numbers in table output
hcloud VPC ListVpcs --cli-output=table --cli-output-num

# Custom endpoint
hcloud ECS ListServersDetails --cli-endpoint=https://ecs.custom.example.com

# Timeouts and retries
hcloud ECS ListServersDetails --cli-connect-timeout=10 --cli-read-timeout=30 --cli-retry-count=3

# Skip SSL verification (not recommended)
hcloud ECS ListServersDetails --cli-skip-secure-verify=true

# JSON input file for complex parameters
hcloud ECS CreateServers --cli-jsonInput=./create-ecs-params.json
```

## Discovery (the "snapshot")

Always query before acting. See [references/discovery.md](references/discovery.md) for full patterns.

```bash
# Networking
hcloud VPC ListVpcs --cli-region=X --cli-output=json --cli-query='vpcs[].{name:name,id:id,cidr:cidr}'
hcloud VPC ListSubnets --cli-region=X --vpc_id=VPC_ID --cli-output=json --cli-query='subnets[].{name:name,id:id,cidr:cidr}'
hcloud VPC ListSecurityGroups --cli-region=X --cli-output=json --cli-query='security_groups[].{name:name,id:id}'
hcloud EIP ListPublicips --cli-region=X --cli-output=json

# Compute
hcloud ECS ListServersDetails --cli-region=X --cli-output=json --cli-query='servers[].{name:name,id:id,status:status,flavor:flavor.id}'
hcloud ECS ListFlavors --cli-region=X --cli-output=json --cli-query='flavors[].{id:id,vcpus:vcpus,ram:ram}'
hcloud IMS ListImages --cli-region=X --__imagetype=gold --__os_type=Linux --cli-output=json --cli-query='images[].{id:id,name:name}'

# Database
hcloud RDS ListDatastores --cli-region=X --database_name=MySQL --cli-output=json
hcloud RDS ListFlavors --cli-region=X --database_name=MySQL --cli-output=json

# IAM
hcloud IAM KeystoneListUsers --cli-output=json --cli-query='users[].{name:name,id:id}'
hcloud IAM KeystoneListProjects --cli-output=json --cli-query='projects[].{name:name,id:id}'
```

## Creation (with dryrun + waiter)

Always dryrun first. See [references/resource-creation.md](references/resource-creation.md) for full patterns.

```bash
# Step 1: Discover existing resources
hcloud VPC ListVpcs --cli-region=la-north-2 --cli-output=json --cli-query='vpcs[].{name:name,id:id}'

# Step 2: Dryrun the create
hcloud --dryrun VPC CreateVpc --cli-region=la-north-2 --vpc.name=demo-vpc --vpc.cidr=10.0.0.0/16

# Step 3: Execute
hcloud VPC CreateVpc --cli-region=la-north-2 --vpc.name=demo-vpc --vpc.cidr=10.0.0.0/16

# Step 4: Verify
hcloud VPC ListVpcs --cli-region=la-north-2 --cli-query='vpcs[?name==`demo-vpc`].{id:id,cidr:cidr}'
```

For async operations, add `--cli-waiter`:

```bash
hcloud ECS CreateServers --cli-region=la-north-2 \
  --cli-waiter='{"expr":"server.status","to":"ACTIVE","timeout":300}' \
  --server.name=demo-ecs \
  --server.flavor_ref=c6.large.2 \
  --server.image_ref=IMAGE_ID \
  --server.availability_zone=la-north-2a \
  --nics.1.subnet_id=SUBNET_ID \
  --nics.1.vpc_id=VPC_ID \
  --security_groups.1.id=SG_ID
```

## Profile & Config

See [references/profile-management.md](references/profile-management.md) for details.

```bash
# Initialize a profile (interactive)
hcloud configure init

# Set AK/SK and region
hcloud configure set --cli-profile=default --access-key=XXX --secret-key=YYY --region=la-north-2

# List profiles
hcloud configure list

# Show current profile
hcloud configure show

# Test connectivity
hcloud configure test

# Delete a profile
hcloud configure delete --cli-profile=old

# SSO authentication
hcloud configure sso
```

## Output & Filtering

```bash
# Full JSON output
hcloud VPC ListVpcs --cli-region=X --cli-output=json

# Project specific fields with JMESPath
hcloud VPC ListVpcs --cli-region=X --cli-output=json --cli-query='vpcs[].{name:name,id:id,cidr:cidr}'

# Filter by name
hcloud VPC ListVpcs --cli-region=X --cli-output=json --cli-query='vpcs[?name==`prod-vpc`].{id:id,cidr:cidr}'

# Table output for human review
hcloud VPC ListVpcs --cli-region=X --cli-output=table --cli-output-num

# JMESPath with nested fields
hcloud ECS ListServersDetails --cli-region=X --cli-output=json --cli-query='servers[].{name:name,status:status,flavor:flavor.id,ips:addresses.private[0].addr}'
```

## Async Operations

See [references/waiter-patterns.md](references/waiter-patterns.md) for per-service patterns.

```bash
# Generic waiter pattern
hcloud <Service> <AsyncOperation> --cli-waiter='{"expr":"<jmespath>","to":"<target>","timeout":<seconds>,"interval":<seconds>}'

# ECS — wait for server to become ACTIVE
hcloud ECS CreateServers ... --cli-waiter='{"expr":"server.status","to":"ACTIVE","timeout":300}'

# RDS — wait for instance to become ACTIVE
hcloud RDS CreateInstance ... --cli-waiter='{"expr":"instances[0].status","to":"ACTIVE","timeout":600}'

# CCE — wait for cluster to become Available
hcloud CCE CreateCluster ... --cli-waiter='{"expr":"status.phase","to":"Available","timeout":600}'
```

## OBS (Object Storage)

OBS is handled by obsutil — a separate tool with its own commands, config, and syntax. See [references/obs.md](references/obs.md) for full reference.

```bash
# Configure OBS separately (different from hcloud configure)
hcloud obs config -e=https://obs.la-north-2.myhuaweicloud.com -i=AK -k=SK

# List buckets
hcloud obs ls -s

# List objects in a bucket
hcloud obs ls obs://my-bucket/ -s

# Upload a file
hcloud obs cp ./file.txt obs://my-bucket/file.txt

# Upload a folder
hcloud obs cp ./folder/ obs://my-bucket/prefix/ -r

# Download
hcloud obs cp obs://my-bucket/file.txt ./file.txt

# Sync (incremental)
hcloud obs sync ./folder/ obs://my-bucket/prefix/

# Create bucket
hcloud obs mb obs://my-bucket -location=la-north-2

# Delete objects
hcloud obs rm obs://my-bucket/old-prefix/ -r -f

# Generate presigned URL
hcloud obs sign obs://my-bucket/file.txt -e=3600
```

## Debug & Meta

```bash
# Debug — print full request/response details
hcloud --debug ECS ListServersDetails --cli-region=la-north-2

# Download latest API metadata
hcloud meta download

# Clear cached metadata
hcloud meta clear

# Configure logging
hcloud log set
hcloud log show

# Update KooCLI
hcloud update

# Version
hcloud version
```

## System Commands

```bash
hcloud configure init     # Interactive profile setup
hcloud configure set      # Set profile values
hcloud configure list     # List all profiles
hcloud configure show     # Show current profile details
hcloud configure delete   # Delete a profile
hcloud configure test     # Test authentication
hcloud configure clear    # Clear all profiles
hcloud configure sso      # SSO authentication
hcloud meta download      # Download API metadata
hcloud meta clear         # Clear metadata cache
hcloud log set            # Configure logging
hcloud log show           # Show log config
hcloud update             # Update KooCLI
hcloud version            # Print version
hcloud auto-complete on   # Enable shell autocomplete
hcloud auto-complete off  # Disable shell autocomplete
```

## Examples

### Example: Discover and create ECS

```bash
# 1. Discover existing networking
hcloud VPC ListVpcs --cli-region=la-north-2 --cli-output=json --cli-query='vpcs[].{name:name,id:id,cidr:cidr}'
# → prod-vpc (10.0.0.0/16) id=e00f74ba-...

hcloud VPC ListSubnets --cli-region=la-north-2 --vpc_id=e00f74ba-59ec-4609-9522-981d8273522f --cli-output=json --cli-query='subnets[].{name:name,id:id,cidr:cidr}'

hcloud VPC ListSecurityGroups --cli-region=la-north-2 --cli-output=json --cli-query='security_groups[].{name:name,id:id}'

# 2. Discover compute options
hcloud ECS ListFlavors --cli-region=la-north-2 --availability_zone=la-north-2a --cli-output=json --cli-query='flavors[].{id:id,name:name,vcpus:vcpus,ram:ram}'

hcloud IMS ListImages --cli-region=la-north-2 --__imagetype=gold --__os_type=Linux --__platform=Ubuntu --cli-output=json --cli-query='images[].{id:id,name:name}'

# 3. Generate skeleton for create
hcloud --skeleton ECS CreateServers

# 4. Dryrun
hcloud --dryrun ECS CreateServers --cli-region=la-north-2 \
  --server.name=demo-ecs \
  --server.flavor_ref=c6.large.2 \
  --server.image_ref=IMAGE_ID \
  --server.availability_zone=la-north-2a \
  --nics.1.subnet_id=SUBNET_ID \
  --nics.1.vpc_id=VPC_ID \
  --security_groups.1.id=SG_ID

# 5. Execute with waiter
hcloud ECS CreateServers --cli-region=la-north-2 \
  --cli-waiter='{"expr":"server.status","to":"ACTIVE","timeout":300}' \
  --server.name=demo-ecs \
  --server.flavor_ref=c6.large.2 \
  --server.image_ref=IMAGE_ID \
  --server.availability_zone=la-north-2a \
  --nics.1.subnet_id=SUBNET_ID \
  --nics.1.vpc_id=VPC_ID \
  --security_groups.1.id=SG_ID

# 6. Verify
hcloud ECS ListServersDetails --cli-region=la-north-2 --name=demo-ecs --cli-output=json --cli-query='servers[].{name:name,id:id,status:status}'
```

### Example: Multi-region query

```bash
# Query the same resource across regions (parallel)
hcloud VPC ListVpcs --cli-region=la-north-2 --cli-output=json --cli-query='vpcs[].{name:name,id:id}'
hcloud VPC ListVpcs --cli-region=ap-southeast-1 --cli-output=json --cli-query='vpcs[].{name:name,id:id}'
hcloud VPC ListVpcs --cli-region=eu-west-101 --cli-output=json --cli-query='vpcs[].{name:name,id:id}'
```

### Example: Find and delete a resource

```bash
# 1. Find by name
hcloud VPC ListVpcs --cli-region=la-north-2 --cli-output=json --cli-query='vpcs[?name==`old-vpc`].id'

# 2. Dryrun delete
hcloud --dryrun VPC DeleteVpc --cli-region=la-north-2 --vpc_id=VPC_ID

# 3. Execute
hcloud VPC DeleteVpc --cli-region=la-north-2 --vpc_id=VPC_ID

# 4. Verify it's gone
hcloud VPC ListVpcs --cli-region=la-north-2 --cli-output=json --cli-query='vpcs[?name==`old-vpc`]'
```

### Example: Upload files to OBS

```bash
# 1. Configure OBS (if not already done)
hcloud obs config -e=https://obs.la-north-2.myhuaweicloud.com -i=AK -k=SK

# 2. List existing buckets
hcloud obs ls -s

# 3. Create bucket if needed
hcloud obs mb obs://my-bucket -location=la-north-2

# 4. Dryrun upload
hcloud obs cp ./data/ obs://my-bucket/data/ -r -dryRun

# 5. Upload
hcloud obs cp ./data/ obs://my-bucket/data/ -r

# 6. Verify
hcloud obs ls obs://my-bucket/data/ -s
```

## Specific tasks

* **Discovering services and operations** [references/service-discovery.md](references/service-discovery.md)
* **Querying existing resources** [references/discovery.md](references/discovery.md)
* **Creating, updating, and deleting resources** [references/resource-creation.md](references/resource-creation.md)
* **Async operation polling patterns** [references/waiter-patterns.md](references/waiter-patterns.md)
* **Profile and authentication management** [references/profile-management.md](references/profile-management.md)
* **Generating Terraform from CLI discoveries** [references/terraform-generation.md](references/terraform-generation.md)
* **Audit and compliance operations** [references/audit-compliance.md](references/audit-compliance.md)
* **OBS object storage (obsutil)** [references/obs.md](references/obs.md)

Base directory for this skill: /home/ubuntu/.opencode/skills/hcloud-cli
Relative paths in this skill (e.g., scripts/, reference/) are relative to this base directory.
Note: file list is sampled.

<skill_files>
<file>/home/ubuntu/.opencode/skills/hcloud-cli/references/obs.md</file>
<file>/home/ubuntu/.opencode/skills/hcloud-cli/references/waiter-patterns.md</file>
<file>/home/ubuntu/.opencode/skills/hcloud-cli/references/profile-management.md</file>
<file>/home/ubuntu/.opencode/skills/hcloud-cli/references/service-discovery.md</file>
<file>/home/ubuntu/.opencode/skills/hcloud-cli/references/discovery.md</file>
<file>/home/ubuntu/.opencode/skills/hcloud-cli/references/terraform-generation.md</file>
<file>/home/ubuntu/.opencode/skills/hcloud-cli/references/audit-compliance.md</file>
<file>/home/ubuntu/.opencode/skills/hcloud-cli/references/resource-creation.md</file>
</skill_files>
</skill_content>
```

**Tool: terraform_get_latest_provider_version**

**Input:**
```json
{
  "namespace": "huaweicloud",
  "name": "huaweicloud"
}
```

**Output:**
```
1.93.0
```

---

## Assistant (Plan · GLM-5.2 · 8.3s)

Let me check the Huawei Cloud CLI config and existing OBS buckets.

**Tool: bash**

**Input:**
```json
{
  "command": "hcloud configure list 2>&1; echo \"---\"; hcloud configure show 2>&1"
}
```

**Output:**
```
{
  "authEncrypt": "true",
  "language": "en",
  "offline": "true",
  "agreePrivacy": "true",
  "warning": "true",
  "current": "default",
  "profiles": [
    {
      "name": "default",
      "mode": "AKSK",
      "accessKeyId": "HPU****AWB",
      "secretAccessKey": "****",
      "securityToken": "",
      "region": "la-north-2",
      "projectId": "",
      "domainId": "",
      "skipSecureVerify": "false",
      "readTimeout": 10,
      "connectTimeout": 5,
      "retryCount": 0
    }
  ]
}
---
{
  "name": "default",
  "mode": "AKSK",
  "accessKeyId": "HPU****AWB",
  "secretAccessKey": "****",
  "securityToken": "",
  "region": "la-north-2",
  "projectId": "",
  "domainId": "",
  "skipSecureVerify": "false",
  "readTimeout": 10,
  "connectTimeout": 5,
  "retryCount": 0
}

```

---

## Assistant (Plan · GLM-5.2 · 6.6s)

**Tool: bash**

**Input:**
```json
{
  "command": "hcloud obs ls -s 2>&1 | head -50"
}
```

**Output:**
```
Start at 2026-06-26 15:19:35.161957566 +0000 UTC

Bucket number: 0

```

---

## Assistant (Plan · GLM-5.2 · 14.1s)

No OBS buckets exist yet. Let me verify OMS availability in the configured region and check available regions.

**Tool: bash**

**Input:**
```json
{
  "command": "hcloud OMS --help 2>&1 | head -40"
}
```

**Output:**
```

KooCLI Version 6.2.9 Copyright(C) 2020-2026 www.huaweicloud.com

Usage:
  hcloud OMS <operation> --param1=value1 --param2=value2 ...

Service:
  OMS

Available Operations:
  BatchUpdateTasks
  CheckPrefix
  CreateSyncEvents
  CreateSyncTask
  CreateTask
  CreateTaskGroup
  DeleteSyncTask
  DeleteTask
  DeleteTaskGroup
  ListApiVersions
  ListSyncTaskStatistic
  ListSyncTasks
  ListTasks
  RetryTaskGroup
  ShowApiInfo
  ShowBucketList
  ShowBucketObjects
  ShowBucketRegion
  ShowCdnInfo
  ShowCloudType
  ShowRegionInfo
  ShowSyncTask
  ShowTask
  ShowTaskGroup
  StartSyncTask
  StartTask
  StartTaskGroup
  StopSyncTask
  StopTask
  StopTaskGroup

```

**Tool: bash**

**Input:**
```json
{
  "command": "hcloud IAM KeystoneListRegions --cli-output=json --cli-query='regions[].{id:id,locale:locale}' 2>&1 | head -80"
}
```

**Output:**
```
[
  {
    "id": "af-north-1",
    "locale": null
  },
  {
    "id": "af-south-1",
    "locale": null
  },
  {
    "id": "ap-southeast-1",
    "locale": null
  },
  {
    "id": "ap-southeast-2",
    "locale": null
  },
  {
    "id": "ap-southeast-3",
    "locale": null
  },
  {
    "id": "ap-southeast-4",
    "locale": null
  },
  {
    "id": "ap-southeast-5",
    "locale": null
  },
  {
    "id": "cn-east-2",
    "locale": null
  },
  {
    "id": "cn-east-201",
    "locale": null
  },
  {
    "id": "cn-east-3",
    "locale": null
  },
  {
    "id": "cn-east-4",
    "locale": null
  },
  {
    "id": "cn-east-5",
    "locale": null
  },
  {
    "id": "cn-north-1",
    "locale": null
  },
  {
    "id": "cn-north-12",
    "locale": null
  },
  {
    "id": "cn-north-219",
    "locale": null
  },
  {
    "id": "cn-north-4",
    "locale": null
  },
  {
    "id": "cn-north-9",
    "locale": null
  },
  {
    "id": "cn-south-1",
    "locale": null
  },
  {
    "id": "cn-south-4",
    "locale": null
  },
  {
    "id": "cn-southwest-2",
    "locale": null

```

---

## Assistant (Plan · GLM-5.2 · 13.3s)

**Tool: bash**

**Input:**
```json
{
  "command": "hcloud OMS ShowRegionInfo --cli-region=la-north-2 --cli-output=json 2>&1 | head -60"
}
```

**Output:**
```
[
  {
    "service_name": "AWS",
    "region_list": [
      {
        "cloud_type": "AWS",
        "value": "us-east-1",
        "description": "US Standard (N. Virginia)"
      },
      {
        "cloud_type": "AWS",
        "value": "us-east-2",
        "description": "US East (Ohio)"
      },
      {
        "cloud_type": "AWS",
        "value": "us-west-1",
        "description": "US West (N. California)"
      },
      {
        "cloud_type": "AWS",
        "value": "us-west-2",
        "description": "US West (Oregon)"
      },
      {
        "cloud_type": "AWS",
        "value": "eu-west-1",
        "description": "EU (Ireland)"
      },
      {
        "cloud_type": "AWS",
        "value": "eu-central-1",
        "description": "EU (Frankfurt)"
      },
      {
        "cloud_type": "AWS",
        "value": "eu-west-2",
        "description": "EU (London)"
      },
      {
        "cloud_type": "AWS",
        "value": "eu-west-3",
        "description": "EU (Paris)"
      },
      {
        "cloud_type": "AWS",
        "value": "eu-south-1",
        "description": "EU (Milanes)"
      },
      {
        "cloud_type": "AWS",
        "value": "eu-north-1",
        "description": "EU (Stockholm)"
      },
      {
        "cloud_type": "AWS",
        "value": "ap-northeast-1",
        "description": "Asia Pacific (Tokyo)"
      },
      {

```

---

## Assistant (Plan · GLM-5.2 · 102.6s)

I have everything needed to plan. Here's the situation:

## Discovery Summary

**AWS S3 source** (`us-east-2`):
- Bucket: `demo-bucket-17b5e8a2` (tag `Name=demo-bucket`)
- 15 objects, ~75 KB each (~1.1 MB total) — "Weekly Report Week N.docx"
- Versioning: Enabled · Encryption: SSE-S3 AES-256 · Storage: STANDARD
- Credentials in `awscredentials.csv` (AK/SK)

**HuaweiCloud destination** (`la-north-2`, profile `default`):
- No OBS buckets exist yet — destination bucket must be created
- OMS service reachable; confirms `us-east-2` is a supported AWS source region

**Terraform** — `huaweicloud` provider **v1.93.0** exposes 3 OMS resources:
| Resource | Use case |
|---|---|
| `huaweicloud_oms_migration_task` | One-shot migration (object/prefix/list/url_list) |
| `huaweicloud_oms_migration_sync_task` | Continuous incremental sync (keeps in sync) |
| `huaweicloud_oms_migration_task_group` | Full-bucket/large migration (PREFIX/LIST/URL_LIST), parallelized |

For 15 small objects, a single `huaweicloud_oms_migration_task` with `type = "prefix"`, `object = [""]` (entire bucket) is the simplest fit. `migration_task_group` is the newer recommended resource for full-bucket migrations and gives better status attributes (`success_num`, `fail_num`, etc.).

A few decisions before I write the Terraform:

**Tool: question**

**Input:**
```json
{
  "questions": [
    {
      "header": "Task type",
      "options": [
        {
          "description": "huaweicloud_oms_migration_task with type=prefix, object=[\"\"] — simplest for 15 small objects, one-shot.",
          "label": "migration_task (one-shot) (Recommended)"
        },
        {
          "description": "huaweicloud_oms_migration_task_group with type=PREFIX — newer, better status attrs, parallelized. Good if bucket grows later.",
          "label": "migration_task_group (one-shot)"
        },
        {
          "description": "huaweicloud_oms_migration_sync_task — keeps OBS in sync with S3 continuously. Use if S3 will keep changing.",
          "label": "migration_sync_task (continuous)"
        }
      ],
      "question": "Which OMS task resource should the Terraform create?"
    },
    {
      "header": "Dest bucket",
      "options": [
        {
          "description": "Same name as the S3 source bucket.",
          "label": "demo-bucket-17b5e8a2"
        },
        {
          "description": "Use the value of the S3 bucket's Name tag.",
          "label": "demo-bucket"
        },
        {
          "description": "Specify a custom OBS bucket name.",
          "label": "I'll provide a name"
        }
      ],
      "question": "Destination OBS bucket name? (must be globally unique, lowercase, 3-63 chars)"
    },
    {
      "header": "Dest storage class",
      "options": [
        {
          "description": "Match S3 STANDARD. Best for frequently accessed data.",
          "label": "STANDARD (Recommended)"
        },
        {
          "description": "Infrequent Access — cheaper storage, higher access cost.",
          "label": "IA"
        }
      ],
      "question": "Destination storage class for migrated objects?"
    },
    {
      "header": "SMN notifications",
      "options": [
        {
          "description": "Skip smn_config block. Simpler; you'll check task status via Terraform/CLI.",
          "label": "No SMN (Recommended)"
        },
        {
          "description": "Add smn_config. You'll need to provide an SMN topic URN.",
          "label": "Yes, I'll provide topic URN"
        }
      ],
      "question": "Enable SMN notifications on task success/failure? (requires an existing SMN topic URN)"
    }
  ]
}
```

**Output:**
```
User has answered your questions: "Which OMS task resource should the Terraform create?"="migration_task (one-shot) (Recommended)", "Destination OBS bucket name? (must be globally unique, lowercase, 3-63 chars)"="demo-bucket-17b5e8a2", "Destination storage class for migrated objects?"="STANDARD (Recommended)", "Enable SMN notifications on task success/failure? (requires an existing SMN topic URN)"="No SMN (Recommended)". You can now continue with the user's answers in mind.
```

---

## Assistant (Plan · GLM-5.2 · 35.2s)

## Proposed Plan

Here's the Terraform I'll write to `/home/ubuntu/code/demo-migration/huaweicloud/oms/`:

### Files to create

**`versions.tf`**
- `terraform { required_providers { huaweicloud = { source = "huaweicloud/huaweicloud", version = "~> 1.93" } } }`

**`variables.tf`** — sensitive creds passed as variables (not hardcoded):
- `aws_source_ak`, `aws_source_sk` (from `awscredentials.csv`)
- `hw_dest_ak`, `hw_dest_sk` (HuaweiCloud AK/SK — same as provider creds)
- `source_region` default `"us-east-2"`, `source_bucket` default `"demo-bucket-17b5e8a2"`
- `dest_region` default `"la-north-2"`, `dest_bucket` default `"demo-bucket-17b5e8a2"`

**`main.tf`**
1. `provider "huaweicloud"` — region `la-north-2`, AK/SK from vars
2. `huaweicloud_obs_bucket` `demo-bucket-17b5e8a2` — region `la-north-2`, storage class STANDARD, tags mirrored from S3 (`Name = demo-bucket`)
3. `huaweicloud_oms_migration_task` `s3_to_obs`:
   - `source_object { data_source = "AWS", region = us-east-2, bucket = demo-bucket-17b5e8a2, access_key/secret_key, object = [""] }`
   - `destination_object { region = la-north-2, bucket = demo-bucket-17b5e8a2, access_key/secret_key }`
   - `type = "object"` with `object = [""]` → migrates entire bucket
   - `dst_storage_policy = "STANDARD"`
   - `enable_metadata_migration = true` (preserve metadata beyond ContentType)
   - `object_overwrite_mode = "SIZE_LAST_MODIFIED_COMPARISON_OVERWRITE"` (safe default)
   - `consistency_check = "size_last_modified"`
   - `start_task = true`, `description = "AWS S3 to HuaweiCloud OBS migration"`

**`outputs.tf`** — `task_id`, `task_name`, `task_status` from the migration task.

**`terraform.tfvars`** — populated from `awscredentials.csv` for the AWS source creds; dest creds reference the HuaweiCloud profile. (Marked sensitive so they won't be printed in plan output.)

### Execution flow (after you approve)
1. `terraform init` → `terraform validate` → `terraform fmt`
2. `terraform plan` — review the OBS bucket create + OMS task create
3. `terraform apply` — creates the OBS bucket, then creates & auto-starts the OMS task (`start_task = true`)
4. Poll `terraform refresh` / `hcloud OMS ShowTask` until `status = 5` (succeeded)
5. Verify with `hcloud obs ls obs://demo-bucket-17b5e8a2/ -s` (expect 15 objects)

### Notes / caveats
- The OBS bucket name `demo-bucket-17b5e8a2` must be globally unique in HuaweiCloud OBS — will confirm at apply time.
- OMS `migration_task` with `type = "object"` and `object = [""]` migrates the whole bucket (15 objects, ~1.1 MB) — completes in seconds.
- AWS source bucket has **versioning enabled**; OMS migrates only current versions by default. If you need all versions, that requires a different approach — let me know.
- Source SSE-S3 AES-256 is transparent; OBS will store objects with its own server-side encryption. `enable_kms` left `false` (would require a KMS key).

Shall I proceed to write the Terraform files?

---

## User

Confirm

---

## Assistant (Build · GLM-5.2 · 21.1s)

Let me get the actual HuaweiCloud AK/SK from the config to populate tfvars.

**Tool: bash**

**Input:**
```json
{
  "command": "cat ~/.hcloud/config.json 2>/dev/null | python3 -c \"import sys,json; c=json.load(sys.stdin); p=[x for x in c['profiles'] if x['name']=='default'][0]; print(p['accessKeyId']); print(p['secretAccessKey'])\" 2>&1"
}
```

**Error:**
```
The user rejected permission to use this specific tool call.
```

---

## User

I just copied the AK SK from huaweicloud to the folder

---

## Assistant (Build · GLM-5.2 · 7.2s)

**Tool: bash**

**Input:**
```json
{
  "command": "ls -la /home/ubuntu/code/demo-migration/huaweicloud/oms/"
}
```

**Output:**
```
total 16
drwxr-xr-x 2 ubuntu ubuntu 4096 Jun 26 10:23 .
drwxr-xr-x 5 ubuntu ubuntu 4096 Jun 26 10:07 ..
-rw-r--r-- 1 ubuntu ubuntu   68 Jun 26 10:14 awscredentials.csv
-rw-r--r-- 1 ubuntu ubuntu  125 Jun 26 10:23 credentials.csv

```

---

## Assistant (Build · GLM-5.2 · 5.3s)

**Tool: read**

**Input:**
```json
{
  "filePath": "/home/ubuntu/code/demo-migration/huaweicloud/oms/credentials.csv"
}
```

**Output:**
```
<path>/home/ubuntu/code/demo-migration/huaweicloud/oms/credentials.csv</path>
<type>file</type>
<content>
1: User Name,Access Key Id,Secret Access Key
2: "bs_dev_J50056672",HPUAH7QPKG3HMQMM3AWB,TY6L8XF9Jjb7K8UcI0KmNtmqo5GAqAsog85cEHsf

(End of file - total 2 lines)
</content>
```

---

## Assistant (Build · GLM-5.2 · 41.8s)

Got both credentials. Writing the Terraform files now.

**Tool: write**

**Input:**
```json
{
  "content": "terraform {\n  required_version = \">= 1.3\"\n\n  required_providers {\n    huaweicloud = {\n      source  = \"huaweicloud/huaweicloud\"\n      version = \"~> 1.93\"\n    }\n  }\n}\n",
  "filePath": "/home/ubuntu/code/demo-migration/huaweicloud/oms/versions.tf"
}
```

**Output:**
```
Wrote file successfully.
```

**Tool: write**

**Input:**
```json
{
  "content": "variable \"source_region\" {\n  description = \"AWS region where the source S3 bucket lives.\"\n  type        = string\n  default     = \"us-east-2\"\n}\n\nvariable \"source_bucket\" {\n  description = \"Name of the source AWS S3 bucket.\"\n  type        = string\n  default     = \"demo-bucket-17b5e8a2\"\n}\n\nvariable \"source_ak\" {\n  description = \"Access key for the source AWS S3 bucket.\"\n  type        = string\n  sensitive   = true\n}\n\nvariable \"source_sk\" {\n  description = \"Secret key for the source AWS S3 bucket.\"\n  type        = string\n  sensitive   = true\n}\n\nvariable \"dest_region\" {\n  description = \"HuaweiCloud region for the destination OBS bucket and OMS task.\"\n  type        = string\n  default     = \"la-north-2\"\n}\n\nvariable \"dest_bucket\" {\n  description = \"Name of the destination HuaweiCloud OBS bucket.\"\n  type        = string\n  default     = \"demo-bucket-17b5e8a2\"\n}\n\nvariable \"dest_ak\" {\n  description = \"Access key for the destination HuaweiCloud OBS bucket.\"\n  type        = string\n  sensitive   = true\n}\n\nvariable \"dest_sk\" {\n  description = \"Secret key for the destination HuaweiCloud OBS bucket.\"\n  type        = string\n  sensitive   = true\n}\n",
  "filePath": "/home/ubuntu/code/demo-migration/huaweicloud/oms/variables.tf"
}
```

**Output:**
```
Wrote file successfully.
```

**Tool: write**

**Input:**
```json
{
  "content": "provider \"huaweicloud\" {\n  region     = var.dest_region\n  access_key = var.dest_ak\n  secret_key = var.dest_sk\n}\n\nresource \"huaweicloud_obs_bucket\" \"destination\" {\n  bucket        = var.dest_bucket\n  region        = var.dest_region\n  storage_class = \"STANDARD\"\n  acl           = \"private\"\n\n  tags = {\n    Name    = \"demo-bucket\"\n    Source  = \"aws-s3\"\n    MigratedBy = \"oms\"\n  }\n}\n\nresource \"huaweicloud_oms_migration_task\" \"s3_to_obs\" {\n  region      = var.dest_region\n  type        = \"object\"\n  description = \"AWS S3 to HuaweiCloud OBS migration\"\n\n  source_object {\n    data_source = \"AWS\"\n    region      = var.source_region\n    bucket      = var.source_bucket\n    access_key  = var.source_ak\n    secret_key  = var.source_sk\n    object      = [\"\"]\n  }\n\n  destination_object {\n    region     = var.dest_region\n    bucket     = huaweicloud_obs_bucket.destination.bucket\n    access_key = var.dest_ak\n    secret_key = var.dest_sk\n  }\n\n  start_task                     = true\n  dst_storage_policy             = \"STANDARD\"\n  enable_metadata_migration      = true\n  enable_failed_object_recording = true\n  object_overwrite_mode          = \"SIZE_LAST_MODIFIED_COMPARISON_OVERWRITE\"\n  consistency_check              = \"size_last_modified\"\n\n  depends_on = [huaweicloud_obs_bucket.destination]\n}\n",
  "filePath": "/home/ubuntu/code/demo-migration/huaweicloud/oms/main.tf"
}
```

**Output:**
```
Wrote file successfully.
```

**Tool: write**

**Input:**
```json
{
  "content": "output \"dest_bucket\" {\n  description = \"Destination OBS bucket name.\"\n  value       = huaweicloud_obs_bucket.destination.bucket\n}\n\noutput \"task_id\" {\n  description = \"OMS migration task ID.\"\n  value       = huaweicloud_oms_migration_task.s3_to_obs.id\n}\n\noutput \"task_name\" {\n  description = \"OMS migration task name.\"\n  value       = huaweicloud_oms_migration_task.s3_to_obs.name\n}\n\noutput \"task_status\" {\n  description = \"OMS migration task status (1=waiting, 2=migrating, 3=paused, 4=failed, 5=succeeded).\"\n  value       = huaweicloud_oms_migration_task.s3_to_obs.status\n}\n",
  "filePath": "/home/ubuntu/code/demo-migration/huaweicloud/oms/outputs.tf"
}
```

**Output:**
```
Wrote file successfully.
```

**Tool: write**

**Input:**
```json
{
  "content": "source_ak = \"YOUR_AWS_ACCESS_KEY_ID\"\nsource_sk = \"YOUR_AWS_SECRET_ACCESS_KEY\"\n\ndest_ak = \"HPUAH7QPKG3HMQMM3AWB\"\ndest_sk = \"TY6L8XF9Jjb7K8UcI0KmNtmqo5GAqAsog85cEHsf\"\n",
  "filePath": "/home/ubuntu/code/demo-migration/huaweicloud/oms/terraform.tfvars"
}
```

**Output:**
```
Wrote file successfully.
```

---

## Assistant (Build · GLM-5.2 · 17.0s)

Now let me init, fmt, and validate.

**Tool: bash**

**Input:**
```json
{
  "command": "terraform init 2>&1 | tail -20",
  "workdir": "/home/ubuntu/code/demo-migration/huaweicloud/oms"
}
```

**Output:**
```
If you'd like to know more about provider signing, you can read about it here:
https://developer.hashicorp.com/terraform/cli/plugins/signing

[0m[1mInitializing the backend...[0m


Terraform has created a lock file [1m.terraform.lock.hcl[0m to record the provider
selections it made above. Include this file in your version control repository
so that Terraform can guarantee to make the same selections by default when
you run "terraform init" in the future.[0m

[0m[1m[32mTerraform has been successfully initialized![0m[32m[0m
[0m[32m
You may now begin working with Terraform. Try running "terraform plan" to see
any changes that are required for your infrastructure. All Terraform commands
should now work.

If you ever set or change modules or backend configuration for Terraform,
rerun this command to reinitialize your working directory. If you forget, other
commands will detect it and remind you to do so if necessary.[0m

```

---

## Assistant (Build · GLM-5.2 · 7.1s)

**Tool: bash**

**Input:**
```json
{
  "command": "terraform fmt 2>&1; echo \"---validate---\"; terraform validate 2>&1",
  "workdir": "/home/ubuntu/code/demo-migration/huaweicloud/oms"
}
```

**Output:**
```
main.tf
---validate---
[32m[1mSuccess![0m The configuration is valid.
[0m

```

---

## Assistant (Build · GLM-5.2 · 13.7s)

Init, fmt, validate all pass. Running `terraform plan` so you can review before apply.

**Tool: bash**

**Input:**
```json
{
  "command": "terraform plan 2>&1 | tail -60",
  "workdir": "/home/ubuntu/code/demo-migration/huaweicloud/oms"
}
```

**Output:**
```
      [32m+[0m[0m region                = "la-north-2"
      [32m+[0m[0m sse_algorithm         = (known after apply)
      [32m+[0m[0m storage_class         = "STANDARD"
      [32m+[0m[0m storage_info          = (known after apply)
      [32m+[0m[0m tags                  = {
          [32m+[0m[0m "MigratedBy" = "oms"
          [32m+[0m[0m "Name"       = "demo-bucket"
          [32m+[0m[0m "Source"     = "aws-s3"
        }
      [32m+[0m[0m user_domain_names     = (known after apply)
      [32m+[0m[0m versioning            = false
    }

[1m  # huaweicloud_oms_migration_task.s3_to_obs[0m will be created
[0m  [32m+[0m[0m resource "huaweicloud_oms_migration_task" "s3_to_obs" {
      [32m+[0m[0m consistency_check              = "size_last_modified"
      [32m+[0m[0m description                    = "AWS S3 to HuaweiCloud OBS migration"
      [32m+[0m[0m dst_storage_policy             = "STANDARD"
      [32m+[0m[0m enable_failed_object_recording = true
      [32m+[0m[0m enable_metadata_migration      = true
      [32m+[0m[0m id                             = (known after apply)
      [32m+[0m[0m migrate_since                  = (known after apply)
      [32m+[0m[0m name                           = (known after apply)
      [32m+[0m[0m object_overwrite_mode          = "SIZE_LAST_MODIFIED_COMPARISON_OVERWRITE"
      [32m+[0m[0m region                         = "la-north-2"
      [32m+[0m[0m start_task                     = true
      [32m+[0m[0m status                         = (known after apply)
      [32m+[0m[0m type                           = "object"

      [32m+[0m[0m destination_object {
          [32m+[0m[0m access_key = (sensitive value)
          [32m+[0m[0m bucket     = "demo-bucket-17b5e8a2"
          [32m+[0m[0m region     = "la-north-2"
          [32m+[0m[0m secret_key = (sensitive value)
        }

      [32m+[0m[0m source_object {
          [32m+[0m[0m access_key  = (sensitive value)
          [32m+[0m[0m bucket      = "demo-bucket-17b5e8a2"
          [32m+[0m[0m data_source = "AWS"
          [32m+[0m[0m object      = [
              [32m+[0m[0m [90mnull[0m[0m,
            ]
          [32m+[0m[0m region      = "us-east-2"
          [32m+[0m[0m secret_key  = (sensitive value)
        }
    }

[1mPlan:[0m [0m2 to add, 0 to change, 0 to destroy.

Changes to Outputs:
  [32m+[0m[0m dest_bucket = "demo-bucket-17b5e8a2"
  [32m+[0m[0m task_id     = (known after apply)
  [32m+[0m[0m task_name   = (known after apply)
  [32m+[0m[0m task_status = (known after apply)
[90m
─────────────────────────────────────────────────────────────────────────────[0m

Note: You didn't use the -out option to save this plan, so Terraform can't
guarantee to take exactly these actions if you run "terraform apply" now.

```

---

## Assistant (Build · GLM-5.2 · 15.0s)

The plan shows `object = [null]` — the empty string got coerced. For full-bucket migration, `type = "prefix"` with `object = [""]` is the correct combination (per the docs). Let me fix that.

**Tool: edit**

**Input:**
```json
{
  "filePath": "/home/ubuntu/code/demo-migration/huaweicloud/oms/main.tf",
  "oldString": "  region      = var.dest_region\n  type        = \"object\"\n  description = \"AWS S3 to HuaweiCloud OBS migration\"",
  "newString": "  region      = var.dest_region\n  type        = \"prefix\"\n  description = \"AWS S3 to HuaweiCloud OBS migration\""
}
```

**Output:**
```
Edit applied successfully.
```

---

## User

Apply

---

## Assistant (Build · GLM-5.2 · 34.7s)

**Tool: bash**

**Input:**
```json
{
  "command": "terraform apply -auto-approve 2>&1 | tail -40",
  "workdir": "/home/ubuntu/code/demo-migration/huaweicloud/oms",
  "timeout": 600000
}
```

**Output:**
```

      [32m+[0m[0m destination_object {
          [32m+[0m[0m access_key = (sensitive value)
          [32m+[0m[0m bucket     = "demo-bucket-17b5e8a2"
          [32m+[0m[0m region     = "la-north-2"
          [32m+[0m[0m secret_key = (sensitive value)
        }

      [32m+[0m[0m source_object {
          [32m+[0m[0m access_key  = (sensitive value)
          [32m+[0m[0m bucket      = "demo-bucket-17b5e8a2"
          [32m+[0m[0m data_source = "AWS"
          [32m+[0m[0m object      = [
              [32m+[0m[0m [90mnull[0m[0m,
            ]
          [32m+[0m[0m region      = "us-east-2"
          [32m+[0m[0m secret_key  = (sensitive value)
        }
    }

[1mPlan:[0m [0m2 to add, 0 to change, 0 to destroy.

Changes to Outputs:
  [32m+[0m[0m dest_bucket = "demo-bucket-17b5e8a2"
  [32m+[0m[0m task_id     = (known after apply)
  [32m+[0m[0m task_name   = (known after apply)
  [32m+[0m[0m task_status = (known after apply)
[0m[1mhuaweicloud_obs_bucket.destination: Creating...[0m[0m
[0m[1mhuaweicloud_obs_bucket.destination: Creation complete after 7s [id=demo-bucket-17b5e8a2][0m
[0m[1mhuaweicloud_oms_migration_task.s3_to_obs: Creating...[0m[0m
[0m[1mhuaweicloud_oms_migration_task.s3_to_obs: Creation complete after 9s [id=260635103393672][0m
[0m[1m[32m
Apply complete! Resources: 2 added, 0 changed, 0 destroyed.[0m
[0m[1m[32m
Outputs:

[0mdest_bucket = "demo-bucket-17b5e8a2"
task_id = "260635103393672"
task_name = "demo-bucket-17b5e8a2-demo-bucket-17b5e8a2-20260626232549510_883"
task_status = 2

```

---

## Assistant (Build · GLM-5.2 · 29.3s)

Apply succeeded — task `260635103393672` is **migrating** (status 2). Let me poll until it completes.

**Tool: bash**

**Input:**
```json
{
  "command": "for i in $(seq 1 12); do\n  status=$(hcloud OMS ShowTask --cli-region=la-north-2 --task_id=260635103393672 --cli-output=json --cli-query='status' 2>/dev/null)\n  echo \"poll $i: status=$status\"\n  if [ \"$status\" = \"5\" ] || [ \"$status\" = \"4\" ]; then break; fi\n  sleep 10\ndone",
  "timeout": 180000
}
```

**Output:**
```
poll 1: status=2
poll 2: status=5

```

---

## Assistant (Build · GLM-5.2 · 8.2s)

Migration succeeded (status 5). Let me verify the objects landed in OBS.

**Tool: bash**

**Input:**
```json
{
  "command": "hcloud obs ls obs://demo-bucket-17b5e8a2/ -s 2>&1 | tail -25"
}
```

**Output:**
```

Folder list:
obs://demo-bucket-17b5e8a2/oms/

Object list:
obs://demo-bucket-17b5e8a2/Weekly Report Week 10.docx
obs://demo-bucket-17b5e8a2/Weekly Report Week 11.docx
obs://demo-bucket-17b5e8a2/Weekly Report Week 12.docx
obs://demo-bucket-17b5e8a2/Weekly Report Week 13.docx
obs://demo-bucket-17b5e8a2/Weekly Report Week 14.docx
obs://demo-bucket-17b5e8a2/Weekly Report Week 15.docx
obs://demo-bucket-17b5e8a2/Weekly Report Week 16.docx
obs://demo-bucket-17b5e8a2/Weekly Report Week 17.docx
obs://demo-bucket-17b5e8a2/Weekly Report Week 18.docx
obs://demo-bucket-17b5e8a2/Weekly Report Week 19.docx
obs://demo-bucket-17b5e8a2/Weekly Report Week 20.docx
obs://demo-bucket-17b5e8a2/Weekly Report Week 21.docx
obs://demo-bucket-17b5e8a2/Weekly Report Week 22.docx
obs://demo-bucket-17b5e8a2/Weekly Report Week 23.docx
obs://demo-bucket-17b5e8a2/Weekly Report Week 24.docx
obs://demo-bucket-17b5e8a2/oms/task/demo-bucket-17b5e8a2-demo-bucket-17b5e8a2-20260626232549510_883/success_object_lists/20260626232552224.success_list.txt

Total size of bucket: 1.09MB
Folder number: 1
File number: 16

```

---

## Assistant (Build · GLM-5.2 · 9.8s)

Migration complete and verified.

## Result

All **15 objects** (~1.09 MB) successfully migrated from AWS S3 `demo-bucket-17b5e8a2` (`us-east-2`) to HuaweiCloud OBS `demo-bucket-17b5e8a2` (`la-north-2`).

- **OBS bucket** created with tags `Name=demo-bucket`, `Source=aws-s3`, `MigratedBy=oms`
- **OMS task** `260635103393672` — status **5 (succeeded)**
- OMS also wrote a success object list under `oms/task/.../success_object_lists/` in the destination bucket (a record of what was migrated)

The Terraform state is saved locally in `/home/ubuntu/code/demo-migration/huaweicloud/oms/`. To tear it all down later: `terraform destroy` (removes the OMS task and the OBS bucket).

---

## User

# Huawei Cloud CLI (KooCLI)

## Rules

1. **DISCOVER before ACT** — always query existing resources with `List`/`Show` operations before creating or modifying anything. Avoid duplicates. Reuse existing infrastructure when possible.
2. **DRYRUN before EXECUTE** — always `--dryrun` create/update/delete calls first. Show the user what will happen. Only execute after confirmation or when the user has explicitly asked to proceed.
3. **Never hardcode IDs** — use resource names to look up IDs via list operations, then reference the IDs. In Terraform output, use data blocks or resource references.
4. **Use JMESPath** — `--cli-query` to filter output and keep token usage minimal. Never dump full API responses when you only need a few fields.
5. **Use waiter** — `--cli-waiter` for async operations (ECS create, RDS create, CCE create, etc.). Never poll manually with sleep loops.
6. **Discover services dynamically** — `hcloud <Service> --help` to find operations; `hcloud <Service> <Operation> --help` to find parameters. Never guess API names or parameters.
7. **Batch independent queries** — call multiple independent list operations in parallel. Only serialize when there's a dependency (subnets need VPC ID, RDS flavors need engine).
8. **Batch questions** — ask related questions together, not one at a time.
9. **OBS is a separate tool** — `hcloud obs` is obsutil, not a standard hcloud API. It uses single-dash flags (`-flag=value`), `obs://bucket/key` URLs, its own config (`~/.obsutilconfig`), and has no JMESPath/JSON output. See [references/obs.md](references/obs.md).

## Quick Start

```bash
# Check CLI is available
hcloud version

# Verify authentication
hcloud configure test

# Discover available services
hcloud --help

# Discover operations for a service
hcloud ECS --help

# Discover parameters for an operation
hcloud ECS ListServersDetails --help

# List existing resources (the "snapshot")
hcloud VPC ListVpcs --cli-region=la-north-2 --cli-output=json --cli-query='vpcs[].{name:name,id:id,cidr:cidr}'

# Preview a create call without executing
hcloud --dryrun VPC CreateVpc --cli-region=la-north-2 --vpc.name=demo-vpc --vpc.cidr=10.0.0.0/16

# Generate a parameter skeleton for complex operations
hcloud --skeleton ECS CreateServers

# Execute with waiter for async operations
hcloud ECS CreateServers --cli-region=la-north-2 --cli-waiter='{"expr":"server.status","to":"ACTIVE","timeout":300}' ...
```

## Core Pattern

```bash
hcloud <Service> <Operation> --param1=value1 --param2=value2
```

- **Service**: cloud service name (ECS, VPC, RDS, IAM, etc.)
- **Operation**: API operation name (ListServersDetails, CreateVpc, etc.)
- **Parameters**: `--param=value` format (always `--param=value`, never `--param value`)

### Parameter naming

- Simple params: `--name=demo-vpc`
- Nested params (body objects): `--vpc.name=demo-vpc --vpc.cidr=10.0.0.0/16`
- Array params: `--nics.1.subnet_id=xxx --nics.1.vpc_id=yyy`
- JSON input for complex bodies: `--cli-jsonInput=./params.json`

## Global Options

```bash
# Preview without executing
hcloud --dryrun ECS CreateServers ...

# Generate parameter skeleton in JSON
hcloud --skeleton ECS CreateServers

# Debug mode — print full request/response
hcloud --debug ECS ListServersDetails --cli-region=la-north-2

# Region override
hcloud ECS ListServersDetails --cli-region=ap-southeast-1

# Profile override
hcloud ECS ListServersDetails --cli-profile=prod

# Output format
hcloud VPC ListVpcs --cli-output=json          # JSON (default for scripting)
hcloud VPC ListVpcs --cli-output=table         # ASCII table
hcloud VPC ListVpcs --cli-output=tsv           # Tab-separated

# JMESPath query — filter and project output
hcloud VPC ListVpcs --cli-query='vpcs[].{name:name,id:id}'

# Async polling
hcloud ECS CreateServers --cli-waiter='{"expr":"server.status","to":"ACTIVE","timeout":300}'

# Row numbers in table output
hcloud VPC ListVpcs --cli-output=table --cli-output-num

# Custom endpoint
hcloud ECS ListServersDetails --cli-endpoint=https://ecs.custom.example.com

# Timeouts and retries
hcloud ECS ListServersDetails --cli-connect-timeout=10 --cli-read-timeout=30 --cli-retry-count=3

# Skip SSL verification (not recommended)
hcloud ECS ListServersDetails --cli-skip-secure-verify=true

# JSON input file for complex parameters
hcloud ECS CreateServers --cli-jsonInput=./create-ecs-params.json
```

## Discovery (the "snapshot")

Always query before acting. See [references/discovery.md](references/discovery.md) for full patterns.

```bash
# Networking
hcloud VPC ListVpcs --cli-region=X --cli-output=json --cli-query='vpcs[].{name:name,id:id,cidr:cidr}'
hcloud VPC ListSubnets --cli-region=X --vpc_id=VPC_ID --cli-output=json --cli-query='subnets[].{name:name,id:id,cidr:cidr}'
hcloud VPC ListSecurityGroups --cli-region=X --cli-output=json --cli-query='security_groups[].{name:name,id:id}'
hcloud EIP ListPublicips --cli-region=X --cli-output=json

# Compute
hcloud ECS ListServersDetails --cli-region=X --cli-output=json --cli-query='servers[].{name:name,id:id,status:status,flavor:flavor.id}'
hcloud ECS ListFlavors --cli-region=X --cli-output=json --cli-query='flavors[].{id:id,vcpus:vcpus,ram:ram}'
hcloud IMS ListImages --cli-region=X --__imagetype=gold --__os_type=Linux --cli-output=json --cli-query='images[].{id:id,name:name}'

# Database
hcloud RDS ListDatastores --cli-region=X --database_name=MySQL --cli-output=json
hcloud RDS ListFlavors --cli-region=X --database_name=MySQL --cli-output=json

# IAM
hcloud IAM KeystoneListUsers --cli-output=json --cli-query='users[].{name:name,id:id}'
hcloud IAM KeystoneListProjects --cli-output=json --cli-query='projects[].{name:name,id:id}'
```

## Creation (with dryrun + waiter)

Always dryrun first. See [references/resource-creation.md](references/resource-creation.md) for full patterns.

```bash
# Step 1: Discover existing resources
hcloud VPC ListVpcs --cli-region=la-north-2 --cli-output=json --cli-query='vpcs[].{name:name,id:id}'

# Step 2: Dryrun the create
hcloud --dryrun VPC CreateVpc --cli-region=la-north-2 --vpc.name=demo-vpc --vpc.cidr=10.0.0.0/16

# Step 3: Execute
hcloud VPC CreateVpc --cli-region=la-north-2 --vpc.name=demo-vpc --vpc.cidr=10.0.0.0/16

# Step 4: Verify
hcloud VPC ListVpcs --cli-region=la-north-2 --cli-query='vpcs[?name==`demo-vpc`].{id:id,cidr:cidr}'
```

For async operations, add `--cli-waiter`:

```bash
hcloud ECS CreateServers --cli-region=la-north-2 \
  --cli-waiter='{"expr":"server.status","to":"ACTIVE","timeout":300}' \
  --server.name=demo-ecs \
  --server.flavor_ref=c6.large.2 \
  --server.image_ref=IMAGE_ID \
  --server.availability_zone=la-north-2a \
  --nics.1.subnet_id=SUBNET_ID \
  --nics.1.vpc_id=VPC_ID \
  --security_groups.1.id=SG_ID
```

## Profile & Config

See [references/profile-management.md](references/profile-management.md) for details.

```bash
# Initialize a profile (interactive)
hcloud configure init

# Set AK/SK and region
hcloud configure set --cli-profile=default --access-key=XXX --secret-key=YYY --region=la-north-2

# List profiles
hcloud configure list

# Show current profile
hcloud configure show

# Test connectivity
hcloud configure test

# Delete a profile
hcloud configure delete --cli-profile=old

# SSO authentication
hcloud configure sso
```

## Output & Filtering

```bash
# Full JSON output
hcloud VPC ListVpcs --cli-region=X --cli-output=json

# Project specific fields with JMESPath
hcloud VPC ListVpcs --cli-region=X --cli-output=json --cli-query='vpcs[].{name:name,id:id,cidr:cidr}'

# Filter by name
hcloud VPC ListVpcs --cli-region=X --cli-output=json --cli-query='vpcs[?name==`prod-vpc`].{id:id,cidr:cidr}'

# Table output for human review
hcloud VPC ListVpcs --cli-region=X --cli-output=table --cli-output-num

# JMESPath with nested fields
hcloud ECS ListServersDetails --cli-region=X --cli-output=json --cli-query='servers[].{name:name,status:status,flavor:flavor.id,ips:addresses.private[0].addr}'
```

## Async Operations

See [references/waiter-patterns.md](references/waiter-patterns.md) for per-service patterns.

```bash
# Generic waiter pattern
hcloud <Service> <AsyncOperation> --cli-waiter='{"expr":"<jmespath>","to":"<target>","timeout":<seconds>,"interval":<seconds>}'

# ECS — wait for server to become ACTIVE
hcloud ECS CreateServers ... --cli-waiter='{"expr":"server.status","to":"ACTIVE","timeout":300}'

# RDS — wait for instance to become ACTIVE
hcloud RDS CreateInstance ... --cli-waiter='{"expr":"instances[0].status","to":"ACTIVE","timeout":600}'

# CCE — wait for cluster to become Available
hcloud CCE CreateCluster ... --cli-waiter='{"expr":"status.phase","to":"Available","timeout":600}'
```

## OBS (Object Storage)

OBS is handled by obsutil — a separate tool with its own commands, config, and syntax. See [references/obs.md](references/obs.md) for full reference.

```bash
# Configure OBS separately (different from hcloud configure)
hcloud obs config -e=https://obs.la-north-2.myhuaweicloud.com -i=AK -k=SK

# List buckets
hcloud obs ls -s

# List objects in a bucket
hcloud obs ls obs://my-bucket/ -s

# Upload a file
hcloud obs cp ./file.txt obs://my-bucket/file.txt

# Upload a folder
hcloud obs cp ./folder/ obs://my-bucket/prefix/ -r

# Download
hcloud obs cp obs://my-bucket/file.txt ./file.txt

# Sync (incremental)
hcloud obs sync ./folder/ obs://my-bucket/prefix/

# Create bucket
hcloud obs mb obs://my-bucket -location=la-north-2

# Delete objects
hcloud obs rm obs://my-bucket/old-prefix/ -r -f

# Generate presigned URL
hcloud obs sign obs://my-bucket/file.txt -e=3600
```

## Debug & Meta

```bash
# Debug — print full request/response details
hcloud --debug ECS ListServersDetails --cli-region=la-north-2

# Download latest API metadata
hcloud meta download

# Clear cached metadata
hcloud meta clear

# Configure logging
hcloud log set
hcloud log show

# Update KooCLI
hcloud update

# Version
hcloud version
```

## System Commands

```bash
hcloud configure init     # Interactive profile setup
hcloud configure set      # Set profile values
hcloud configure list     # List all profiles
hcloud configure show     # Show current profile details
hcloud configure delete   # Delete a profile
hcloud configure test     # Test authentication
hcloud configure clear    # Clear all profiles
hcloud configure sso      # SSO authentication
hcloud meta download      # Download API metadata
hcloud meta clear         # Clear metadata cache
hcloud log set            # Configure logging
hcloud log show           # Show log config
hcloud update             # Update KooCLI
hcloud version            # Print version
hcloud auto-complete on   # Enable shell autocomplete
hcloud auto-complete off  # Disable shell autocomplete
```

## Examples

### Example: Discover and create ECS

```bash
# 1. Discover existing networking
hcloud VPC ListVpcs --cli-region=la-north-2 --cli-output=json --cli-query='vpcs[].{name:name,id:id,cidr:cidr}'
# → prod-vpc (10.0.0.0/16) id=e00f74ba-...

hcloud VPC ListSubnets --cli-region=la-north-2 --vpc_id=e00f74ba-59ec-4609-9522-981d8273522f --cli-output=json --cli-query='subnets[].{name:name,id:id,cidr:cidr}'

hcloud VPC ListSecurityGroups --cli-region=la-north-2 --cli-output=json --cli-query='security_groups[].{name:name,id:id}'

# 2. Discover compute options
hcloud ECS ListFlavors --cli-region=la-north-2 --availability_zone=la-north-2a --cli-output=json --cli-query='flavors[].{id:id,name:name,vcpus:vcpus,ram:ram}'

hcloud IMS ListImages --cli-region=la-north-2 --__imagetype=gold --__os_type=Linux --__platform=Ubuntu --cli-output=json --cli-query='images[].{id:id,name:name}'

# 3. Generate skeleton for create
hcloud --skeleton ECS CreateServers

# 4. Dryrun
hcloud --dryrun ECS CreateServers --cli-region=la-north-2 \
  --server.name=demo-ecs \
  --server.flavor_ref=c6.large.2 \
  --server.image_ref=IMAGE_ID \
  --server.availability_zone=la-north-2a \
  --nics.1.subnet_id=SUBNET_ID \
  --nics.1.vpc_id=VPC_ID \
  --security_groups.1.id=SG_ID

# 5. Execute with waiter
hcloud ECS CreateServers --cli-region=la-north-2 \
  --cli-waiter='{"expr":"server.status","to":"ACTIVE","timeout":300}' \
  --server.name=demo-ecs \
  --server.flavor_ref=c6.large.2 \
  --server.image_ref=IMAGE_ID \
  --server.availability_zone=la-north-2a \
  --nics.1.subnet_id=SUBNET_ID \
  --nics.1.vpc_id=VPC_ID \
  --security_groups.1.id=SG_ID

# 6. Verify
hcloud ECS ListServersDetails --cli-region=la-north-2 --name=demo-ecs --cli-output=json --cli-query='servers[].{name:name,id:id,status:status}'
```

### Example: Multi-region query

```bash
# Query the same resource across regions (parallel)
hcloud VPC ListVpcs --cli-region=la-north-2 --cli-output=json --cli-query='vpcs[].{name:name,id:id}'
hcloud VPC ListVpcs --cli-region=ap-southeast-1 --cli-output=json --cli-query='vpcs[].{name:name,id:id}'
hcloud VPC ListVpcs --cli-region=eu-west-101 --cli-output=json --cli-query='vpcs[].{name:name,id:id}'
```

### Example: Find and delete a resource

```bash
# 1. Find by name
hcloud VPC ListVpcs --cli-region=la-north-2 --cli-output=json --cli-query='vpcs[?name==`old-vpc`].id'

# 2. Dryrun delete
hcloud --dryrun VPC DeleteVpc --cli-region=la-north-2 --vpc_id=VPC_ID

# 3. Execute
hcloud VPC DeleteVpc --cli-region=la-north-2 --vpc_id=VPC_ID

# 4. Verify it's gone
hcloud VPC ListVpcs --cli-region=la-north-2 --cli-output=json --cli-query='vpcs[?name==`old-vpc`]'
```

### Example: Upload files to OBS

```bash
# 1. Configure OBS (if not already done)
hcloud obs config -e=https://obs.la-north-2.myhuaweicloud.com -i=AK -k=SK

# 2. List existing buckets
hcloud obs ls -s

# 3. Create bucket if needed
hcloud obs mb obs://my-bucket -location=la-north-2

# 4. Dryrun upload
hcloud obs cp ./data/ obs://my-bucket/data/ -r -dryRun

# 5. Upload
hcloud obs cp ./data/ obs://my-bucket/data/ -r

# 6. Verify
hcloud obs ls obs://my-bucket/data/ -s
```

## Specific tasks

* **Discovering services and operations** [references/service-discovery.md](references/service-discovery.md)
* **Querying existing resources** [references/discovery.md](references/discovery.md)
* **Creating, updating, and deleting resources** [references/resource-creation.md](references/resource-creation.md)
* **Async operation polling patterns** [references/waiter-patterns.md](references/waiter-patterns.md)
* **Profile and authentication management** [references/profile-management.md](references/profile-management.md)
* **Generating Terraform from CLI discoveries** [references/terraform-generation.md](references/terraform-generation.md)
* **Audit and compliance operations** [references/audit-compliance.md](references/audit-compliance.md)
* **OBS object storage (obsutil)** [references/obs.md](references/obs.md)


That is so good, I have a question, could you have done that with hcloud instead of terraform?

---

## Assistant (Plan · GLM-5.2 · 31.1s)

Yes, absolutely. The OMS service is fully exposed in KooCLI. The equivalent hcloud flow would be:

```bash
# 1. Create the destination OBS bucket
hcloud obs mb obs://demo-bucket-17b5e8a2 -location=la-north-2

# 2. Dryrun the OMS task creation
hcloud --dryrun OMS CreateTask --cli-region=la-north-2 \
  --type=object \
  --description="AWS S3 to HuaweiCloud OBS migration" \
  --src_node.data_source=AWS \
  --src_node.region=us-east-2 \
  --src_node.bucket=demo-bucket-17b5e8a2 \
  --src_node.access_key=AKIA... \
  --src_node.secret_key=VLIv... \
  --src_node.object.1="" \
  --dst_node.region=la-north-2 \
  --dst_node.bucket=demo-bucket-17b5e8a2 \
  --dst_node.access_key=HPUA... \
  --dst_node.secret_key=TY6L... \
  --dst_storage_policy=STANDARD \
  --enable_metadata_migration=true \
  --start_task=true

# 3. Execute (returns task_id)
hcloud OMS CreateTask --cli-region=la-north-2 ... 

# 4. Poll until status=5 (use ShowTask, or a waiter)
hcloud OMS ShowTask --cli-region=la-north-2 --task_id=<ID> \
  --cli-query='status'

# 5. Verify
hcloud obs ls obs://demo-bucket-17b5e8a2/ -s
```

### Terraform vs hcloud — trade-offs for this task

| | **Terraform** | **hcloud CLI** |
|---|---|---|
| State tracking | State file; `terraform destroy` cleans up | No state; manual cleanup via `DeleteTask` + `obs rm` |
| Reusability/repeatability | Versioned `.tf` files, easy to rerun/clone | One-off scripts; harder to reproduce at scale |
| Drift management | `plan` shows drift vs real cloud | Manual; you re-query each time |
| Speed for a one-off | Heavier (init/plan/apply) | Lighter, direct API calls |
| Best for | Repeatable, reviewed, IaC-governed migrations | Quick ad-hoc migrations, scripting, CI steps |
| Credentials | Variables, sensitive-flagged | Inline flags (must avoid shell history) |

**When to pick which:**
- **Terraform** (what we did) — best when the migration is part of a repo, needs review/approval, or you'll repeat it across environments/regions. The OMS task and OBS bucket become managed resources you can inspect, update, and tear down declaratively.
- **hcloud CLI** — best for a one-shot migration, a quick validation, or embedding into a shell/CI pipeline where you don't want Terraform state overhead. You'd use `--dryrun` first, then execute, then poll with `ShowTask`.

For this specific case (single bucket, 15 objects, one-time), hcloud would have been faster to run. Terraform was the better choice because you asked for it and it leaves a reusable, reviewable artifact in the repo — useful if you later migrate more buckets by parameterizing the module.

Want me to also produce the equivalent hcloud script as a `migrate.sh` alongside the Terraform, so you have both options?

---

