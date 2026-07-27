# OBS — Object Storage Service (obsutil)

OBS in KooCLI is **not** a standard `hcloud <Service> <Operation>` API. It is a separate tool called **obsutil** (v5.5.9) embedded as `hcloud obs`. It has its own configuration, command syntax, and parameter format.

## OBS vs standard hcloud

| Aspect | Standard hcloud | OBS (obsutil) |
|--------|----------------|---------------|
| **Invocation** | `hcloud <Service> <Operation> --param=value` | `hcloud obs <command> [args] -flag=value` |
| **Flag format** | `--double-dash=value` | `-single-dash=value` |
| **Resource addressing** | `--resource_id=xxx` | `obs://bucket/key` URL format |
| **Config** | `hcloud configure set` → `~/.hcloud/` | `hcloud obs config` → `~/.obsutilconfig` |
| **Auth** | Shares hcloud profile AK/SK | Separate AK/SK + endpoint in obsutilconfig |
| **Help** | `hcloud <Service> <Operation> --help` | `hcloud obs help <command>` |
| **Dryrun** | `--dryrun` global flag | `-dryRun` command flag (cp, sync, mv only) |
| **Output** | `--cli-output=json --cli-query=...` | Text output only; no JSON/JMESPath |
| **Skeleton** | `--skeleton` | Not available |
| **Waiter** | `--cli-waiter='...'` | Not available |
| **Version** | `hcloud version` | `hcloud obs version` |

**Critical**: Do not mix hcloud and obsutil flag formats. OBS always uses single-dash flags (`-e=`, `-i=`, `-k=`) and `obs://` URLs.

## Configuration

OBS has its own config file at `~/.obsutilconfig`, separate from hcloud profiles.

### Interactive setup

```bash
hcloud obs config -interactive
```

### Set config directly

```bash
# Set endpoint, AK, SK
hcloud obs config -e=https://obs.la-north-2.myhuaweicloud.com -i=YOUR_AK -k=YOUR_SK

# With temporary token
hcloud obs config -e=https://obs.la-north-2.myhuaweicloud.com -i=TEMP_AK -k=TEMP_SK -t=TEMP_TOKEN

# Custom config file path
hcloud obs config -config=/path/to/custom-config -e=ENDPOINT -i=AK -k=SK
```

### Endpoint format

```
https://obs.<region>.myhuaweicloud.com
```

Common endpoints:

| Region | Endpoint |
|--------|----------|
| la-north-2 | `https://obs.la-north-2.myhuaweicloud.com` |
| ap-southeast-1 | `https://obs.ap-southeast-1.myhuaweicloud.com` |
| ap-southeast-3 | `https://obs.ap-southeast-3.myhuaweicloud.com` |
| eu-west-101 | `https://obs.eu-west-101.myhuaweicloud.com` |
| af-south-1 | `https://obs.af-south-1.myhuaweicloud.com` |

### Inline auth override

Any OBS command accepts `-e=`, `-i=`, `-k=`, `-t=` flags to override the config file for that single invocation:

```bash
hcloud obs ls -s -e=https://obs.ap-southeast-1.myhuaweicloud.com -i=AK -k=SK
```

### Config file location

Default: `~/.obsutilconfig`

Override with `-config=xxx` on any command.

## URL format

All OBS operations use `obs://` URLs:

```
obs://bucket                    # Bucket level
obs://bucket/key                # Specific object
obs://bucket/prefix/            # Prefix (folder) level
```

## Bucket management

### List buckets

```bash
# List all buckets (brief)
hcloud obs ls -s

# List with storage class
hcloud obs ls -s -sc

# Limit results
hcloud obs ls -s -limit=10
```

### Create bucket

```bash
# Create in a region
hcloud obs mb obs://my-bucket -location=la-north-2

# With ACL and storage class
hcloud obs mb obs://my-bucket -location=la-north-2 -acl=private -sc=standard

# Public-read bucket
hcloud obs mb obs://public-bucket -location=la-north-2 -acl=public-read

# POSIX bucket
hcloud obs mb obs://posix-bucket -location=la-north-2 -fs

# Multi-AZ bucket
hcloud obs mb obs://ha-bucket -location=la-north-2 -az=multi-az
```

ACL values: `private`, `public-read`, `public-read-write`

Storage class values: `standard`, `warm`, `cold`, `deep-archive`

### Delete bucket

```bash
# Delete empty bucket
hcloud obs rm obs://my-bucket -f
```

### Bucket properties

```bash
# Show bucket properties
hcloud obs stat obs://my-bucket

# Show bucket ACL
hcloud obs stat obs://my-bucket -acl
```

### Set bucket attributes

```bash
# Set storage class
hcloud obs chattri obs://my-bucket -sc=warm

# Set ACL
hcloud obs chattri obs://my-bucket -acl=public-read

# Set bucket policy (from JSON file)
hcloud obs bucketpolicy obs://my-bucket -method=put -localfile=./policy.json

# Get bucket policy
hcloud obs bucketpolicy obs://my-bucket -method=get -localfile=./policy.json

# Delete bucket policy
hcloud obs bucketpolicy obs://my-bucket -method=delete
```

## Object management

### List objects

```bash
# List all objects in a bucket
hcloud obs ls obs://my-bucket/ -s

# List with details (size, date)
hcloud obs ls obs://my-bucket/

# List objects in a prefix (folder)
hcloud obs ls obs://my-bucket/logs/ -s

# List only current folder (not recursive)
hcloud obs ls obs://my-bucket/ -s -d

# List with human-readable sizes
hcloud obs ls obs://my-bucket/ -s -bf=human-readable

# Limit results
hcloud obs ls obs://my-bucket/ -s -limit=100

# Pagination with marker
hcloud obs ls obs://my-bucket/ -s -limit=100 -marker=last_object_key

# List object versions (versioned bucket)
hcloud obs ls obs://my-bucket/ -s -v

# Get total size of a prefix
hcloud obs ls obs://my-bucket/logs/ -s -du
```

### Upload

```bash
# Upload a single file
hcloud obs cp ./file.txt obs://my-bucket/path/file.txt

# Upload a folder recursively
hcloud obs cp ./my-folder/ obs://my-bucket/prefix/ -r

# Upload with storage class
hcloud obs cp ./data.tar.gz obs://my-bucket/archives/ -sc=cold

# Upload with ACL
hcloud obs cp ./report.pdf obs://my-bucket/reports/ -acl=public-read

# Upload with custom metadata
hcloud obs cp ./file.txt obs://my-bucket/file.txt -meta=author:john#version:1.0

# Dryrun (preview without uploading)
hcloud obs cp ./file.txt obs://my-bucket/file.txt -dryRun

# Upload only changed files
hcloud obs cp ./my-folder/ obs://my-bucket/prefix/ -r -u

# Upload with include/exclude filters
hcloud obs cp ./logs/ obs://my-bucket/logs/ -r -include=*.log -exclude=*.tmp

# Upload with time range filter
hcloud obs cp ./logs/ obs://my-bucket/logs/ -r -timeRange=2026-01-01T00:00:00-2026-06-01T00:00:00
```

### Download

```bash
# Download a single object
hcloud obs cp obs://my-bucket/path/file.txt ./file.txt

# Download a folder recursively
hcloud obs cp obs://my-bucket/prefix/ ./my-folder/ -r

# Download a specific version
hcloud obs cp obs://my-bucket/file.txt ./file.txt -versionId=VERSION_ID

# Download with include/exclude
hcloud obs cp obs://my-bucket/logs/ ./logs/ -r -include=*.log

# Dryrun download
hcloud obs cp obs://my-bucket/file.txt ./file.txt -dryRun
```

### Copy between buckets

```bash
# Copy single object
hcloud obs cp obs://src-bucket/key obs://dst-bucket/key

# Copy a prefix recursively
hcloud obs cp obs://src-bucket/prefix/ obs://dst-bucket/prefix/ -r

# Copy with different storage class
hcloud obs cp obs://src-bucket/data/ obs://dst-bucket/archive/ -r -sc=cold

# Cross-region copy (needs endpoint override for destination)
hcloud obs cp obs://src-bucket/key obs://dst-bucket/key -e=https://obs.ap-southeast-1.myhuaweicloud.com
```

### Move

```bash
# Move single object (copy + delete source)
hcloud obs mv obs://src-bucket/key obs://dst-bucket/key

# Move prefix recursively
hcloud obs mv obs://src-bucket/old-prefix/ obs://dst-bucket/new-prefix/ -r

# Dryrun move
hcloud obs mv obs://src-bucket/key obs://dst-bucket/key -dryRun
```

### Delete objects

```bash
# Delete single object
hcloud obs rm obs://my-bucket/path/file.txt -f

# Delete all objects with a prefix
hcloud obs rm obs://my-bucket/old-prefix/ -r -f

# Delete specific version
hcloud obs rm obs://my-bucket/file.txt -f -versionId=VERSION_ID

# Delete all versions and delete markers
hcloud obs rm obs://my-bucket/prefix/ -r -f -v
```

### View object content

```bash
# Print text object to stdout
hcloud obs cat obs://my-bucket/config.json
```

### Object properties

```bash
# Show object metadata
hcloud obs stat obs://my-bucket/file.txt

# Show object ACL
hcloud obs stat obs://my-bucket/file.txt -acl
```

### Set object attributes

```bash
# Change storage class
hcloud obs chattri obs://my-bucket/file.txt -sc=warm

# Change ACL
hcloud obs chattri obs://my-bucket/file.txt -acl=public-read

# Batch change storage class for a prefix
hcloud obs chattri obs://my-bucket/logs/ -r -f -sc=cold
```

### Create folder

```bash
hcloud obs mkdir obs://my-bucket/folder1/folder2/
```

## Sync

Incremental sync — only transfers changed files. Use instead of `cp -r -u` for ongoing synchronization.

```bash
# Sync local folder to bucket
hcloud obs sync ./my-folder/ obs://my-bucket/prefix/

# Sync bucket to local
hcloud obs sync obs://my-bucket/prefix/ ./my-folder/

# Sync between buckets
hcloud obs sync obs://src-bucket/ obs://dst-bucket/

# Dryrun sync
hcloud obs sync ./my-folder/ obs://my-bucket/prefix/ -dryRun

# Sync with filters
hcloud obs sync ./logs/ obs://my-bucket/logs/ -include=*.log -exclude=*.tmp
```

## Lifecycle rules

```bash
# Get lifecycle rules to a JSON file
hcloud obs lifecycle obs://my-bucket -method=get -localfile=./lifecycle.json

# Put lifecycle rules from a JSON file
hcloud obs lifecycle obs://my-bucket -method=put -localfile=./lifecycle.json

# Delete all lifecycle rules
hcloud obs lifecycle obs://my-bucket -method=delete
```

## Cold storage restore

Restore cold/frozen objects to readable state temporarily:

```bash
# Restore single cold object for 7 days
hcloud obs restore obs://my-bucket/archive.zip -d=7

# Restore with expedited speed
hcloud obs restore obs://my-bucket/urgent.dat -d=1 -t=expedited

# Batch restore a prefix
hcloud obs restore obs://my-bucket/archives/ -r -f -d=7
```

## Multipart uploads

```bash
# List multipart uploads
hcloud obs ls obs://my-bucket/ -s -m

# List both objects and multipart uploads
hcloud obs ls obs://my-bucket/ -s -a

# Abort a specific multipart upload
hcloud obs abort obs://my-bucket/key -u=UPLOAD_ID -f

# Abort all multipart uploads with a prefix
hcloud obs abort obs://my-bucket/prefix/ -r -f
```

## Presigned URLs

```bash
# Generate a download URL (default 300s expiry)
hcloud obs sign obs://my-bucket/file.txt

# Custom expiry (1 hour)
hcloud obs sign obs://my-bucket/file.txt -e=3600

# Batch generate URLs for a prefix
hcloud obs sign obs://my-bucket/reports/ -r -e=7200 -o=./urls/
```

## Sharing

```bash
# Create authorization code for sharing
hcloud obs create-share obs://my-bucket/data/ -vp=7d

# List shared objects using authorization code
hcloud obs share-ls AUTH_CODE -ac=ACCESS_CODE -s

# Download shared objects
hcloud obs share-cp AUTH_CODE ./download/ -key=data/file.csv -ac=ACCESS_CODE
```

## Performance options

For large uploads/downloads, tune concurrency:

```bash
# -j=N : concurrent jobs (batch operations)
# -p=N : concurrent tasks per job (multipart parts)
# -ps=auto : part size (auto, or bytes like 94371840)
# -threshold=N : multipart threshold in bytes (default 50MB)

# Upload large folder with high concurrency
hcloud obs cp ./big-folder/ obs://my-bucket/data/ -r -j=5 -p=5

# Upload with custom part size
hcloud obs cp ./large-file.tar obs://my-bucket/ -ps=94371840 -threshold=104857600
```

Defaults (from config file):
- `maxConnections`: 1000
- `defaultBigfileThreshold`: 52428800 (50 MB)
- `defaultPartSize`: auto
- `defaultParallels`: 5 (tasks per job)
- `defaultJobs`: 5 (concurrent jobs)

## Verification options

```bash
# Verify file size after upload/download
hcloud obs cp ./file obs://bucket/file -vlength

# Verify MD5 after upload/download
hcloud obs cp ./file obs://bucket/file -vmd5

# Both
hcloud obs cp ./file obs://bucket/file -vlength -vmd5
```

## Utilities

### Hash calculation

```bash
# MD5 of a local file
hcloud obs hash ./file.txt -type=md5

# CRC64
hcloud obs hash ./file.txt -type=crc64
```

### Archive logs

```bash
# Archive obsutil logs to local filesystem
hcloud obs archive ./log-archive/

# Archive logs to OBS
hcloud obs archive obs://my-bucket/logs/
```

### Clear part records

```bash
# Clear all part records
hcloud obs clear

# Clear upload part records only
hcloud obs clear -u

# Clear download part records only
hcloud obs clear -d

# Clear copy part records only
hcloud obs clear -c
```

### Update obsutil

```bash
hcloud obs update
```

## Common workflows

### Upload a website to OBS

```bash
# 1. Create bucket
hcloud obs mb obs://my-website -location=la-north-2 -acl=public-read

# 2. Upload static files
hcloud obs cp ./dist/ obs://my-website/ -r -acl=public-read

# 3. Verify
hcloud obs ls obs://my-website/ -s
```

### Backup logs to cold storage

```bash
# 1. Upload to cold storage
hcloud obs cp ./logs/ obs://log-archive/2026-06/ -r -sc=cold

# 2. Set lifecycle to auto-delete after 365 days
# (create lifecycle.json first, then apply)
hcloud obs lifecycle obs://log-archive -method=put -localfile=./lifecycle.json
```

### Sync local data to OBS

```bash
# Initial sync
hcloud obs sync ./data/ obs://my-bucket/data/

# Ongoing incremental sync (only changed files)
hcloud obs sync ./data/ obs://my-bucket/data/ -j=3 -p=5
```

### Download and restore cold archives

```bash
# 1. Restore cold object (takes minutes to hours)
hcloud obs restore obs://archive-bucket/old-data.zip -d=7

# 2. Wait for restore to complete, then download
hcloud obs cp obs://archive-bucket/old-data.zip ./old-data.zip
```

## Best practices

1. **Configure OBS separately** — `hcloud obs config` has its own AK/SK and endpoint, independent of `hcloud configure`.
2. **Use `-s` for brief output** — full listings are verbose; `-s` keeps output token-efficient.
3. **Use `sync` over `cp -r -u`** — sync is purpose-built for incremental transfers.
4. **Use `-dryRun` before large operations** — preview what cp/sync/mv will do.
5. **Use `-j` and `-p` for large transfers** — increase concurrency for batch operations.
6. **Use `-include`/`-exclude` filters** — avoid transferring unwanted files.
7. **Use `-sc=cold` for archives** — cold storage is cheaper; use lifecycle rules to auto-transition.
8. **Use `-vlength -vmd5` for critical data** — verify integrity after transfer.
9. **Use `-f` for batch deletions** — force mode skips confirmation prompts.
10. **Clean up multipart uploads** — `hcloud obs ls obs://bucket/ -s -m` to find abandoned uploads, then `abort` them.
