variable "aws_region" {
  type        = string
  description = "Region de AWS donde esta el bucket S3 origen."
}

variable "aws_bucket" {
  type        = string
  description = "Nombre del bucket S3 origen."
}

variable "aws_ak" {
  type        = string
  sensitive   = true
  description = "Access Key ID de AWS con permisos s3:GetObject y s3:ListBucket sobre el bucket origen."
}

variable "aws_sk" {
  type        = string
  sensitive   = true
  description = "Secret Access Key de AWS."
}

variable "hc_region" {
  type        = string
  default     = "la-north-2"
  description = "Region de Huawei Cloud donde se crea el bucket OBS destino y la tarea OMS."
}

variable "hc_bucket" {
  type        = string
  description = "Nombre del bucket OBS destino (globalmente unico, minusculas)."
}

variable "hc_ak" {
  type        = string
  sensitive   = true
  description = "Access Key ID de Huawei Cloud con permisos OBS sobre el bucket destino."
}

variable "hc_sk" {
  type        = string
  sensitive   = true
  description = "Secret Access Key de Huawei Cloud."
}
