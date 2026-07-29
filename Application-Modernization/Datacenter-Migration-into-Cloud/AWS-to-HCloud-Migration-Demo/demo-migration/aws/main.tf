terraform {
  required_providers {
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }
}

provider "aws" {
  region = "us-east-2"
}

resource "tls_private_key" "ssh" {
  algorithm = "ED25519"
}

resource "aws_key_pair" "demo" {
  key_name   = "demo-ssh-key"
  public_key = tls_private_key.ssh.public_key_openssh

  tags = {
    Name = "demo-ssh-key"
  }
}

resource "random_password" "wp_auth_key" {
  length  = 64
  special = false
}

resource "random_password" "wp_secure_auth_key" {
  length  = 64
  special = false
}

resource "random_password" "wp_logged_in_key" {
  length  = 64
  special = false
}

resource "random_password" "wp_nonce_key" {
  length  = 64
  special = false
}

resource "random_password" "wp_auth_salt" {
  length  = 64
  special = false
}

resource "random_password" "wp_secure_auth_salt" {
  length  = 64
  special = false
}

resource "random_password" "wp_logged_in_salt" {
  length  = 64
  special = false
}

resource "random_password" "wp_nonce_salt" {
  length  = 64
  special = false
}

data "aws_ami" "ubuntu_2204" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}
