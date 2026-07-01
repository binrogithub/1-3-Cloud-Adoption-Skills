resource "huaweicloud_obs_bucket" "this" {
  bucket = lower(var.bucket_name)
  acl    = "private"

  # TODO: Enable server-side encryption/KMS when required by the deployment pattern.
}

resource "huaweicloud_obs_bucket_object" "prefixes" {
  for_each = toset(["landing/", "bronze/", "silver/", "gold/", "scripts/", "logs/", "tmp/"])
  bucket   = huaweicloud_obs_bucket.this.bucket
  key      = each.value
  content  = ""
}
