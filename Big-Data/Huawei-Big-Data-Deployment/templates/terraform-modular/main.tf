locals {
  name_prefix = "${var.project}-${var.env}"
  common_tags = {
    project = var.project
    env     = var.env
    managed = "terraform"
    skill   = "Huawei-Big-Data-Deployment"
  }
}

module "vpc" {
  source      = "./modules/vpc"
  name_prefix = local.name_prefix
  vpc_cidr    = var.vpc_cidr
  subnet_cidr = var.subnet_cidr
}

module "security" {
  source           = "./modules/security"
  name_prefix      = local.name_prefix
  vpc_id           = module.vpc.vpc_id
  allowed_ssh_cidr = var.allowed_ssh_cidr
  subnet_cidr      = var.subnet_cidr
}

module "obs" {
  source      = "./modules/obs"
  bucket_name = "${local.name_prefix}-obs-${var.region}"
}

module "iam_agency" {
  source      = "./modules/iam-agency"
  name_prefix = local.name_prefix
}

module "kms" {
  count       = var.enable_kms ? 1 : 0
  source      = "./modules/kms"
  name_prefix = local.name_prefix
}

module "bastion" {
  count             = var.enable_bastion ? 1 : 0
  source            = "./modules/bastion"
  name_prefix       = local.name_prefix
  vpc_id            = module.vpc.vpc_id
  subnet_id         = module.vpc.subnet_id
  security_group_id = module.security.bastion_security_group_id
  availability_zone = var.availability_zone
}

module "mrs" {
  count             = var.enable_mrs ? 1 : 0
  source            = "./modules/mrs"
  name_prefix       = local.name_prefix
  vpc_id            = module.vpc.vpc_id
  subnet_id         = module.vpc.subnet_id
  security_group_id = module.security.bigdata_security_group_id
  agency_name       = module.iam_agency.agency_name
  availability_zone = var.availability_zone
}

module "dws" {
  count             = var.enable_dws ? 1 : 0
  source            = "./modules/dws"
  name_prefix       = local.name_prefix
  vpc_id            = module.vpc.vpc_id
  subnet_id         = module.vpc.subnet_id
  security_group_id = module.security.bigdata_security_group_id
  availability_zone = var.availability_zone
}

module "dli" {
  count       = var.enable_dli ? 1 : 0
  source      = "./modules/dli"
  name_prefix = local.name_prefix
}

module "cdm" {
  count             = var.enable_cdm ? 1 : 0
  source            = "./modules/cdm"
  name_prefix       = local.name_prefix
  vpc_id            = module.vpc.vpc_id
  subnet_id         = module.vpc.subnet_id
  security_group_id = module.security.bigdata_security_group_id
}
