resource "huaweicloud_kms_key" "this" {
  key_alias   = "${var.name_prefix}-kms"
  key_usage   = "ENCRYPT_DECRYPT"
  description = "KMS key for big data platform encryption"
}
