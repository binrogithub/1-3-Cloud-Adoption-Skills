provider "huaweicloud" {
  region = var.region

  # Credentials are read from environment variables (HW_ACCESS_KEY, HW_SECRET_KEY).
  # NEVER hardcode credentials in this file or in .tfvars.
}
