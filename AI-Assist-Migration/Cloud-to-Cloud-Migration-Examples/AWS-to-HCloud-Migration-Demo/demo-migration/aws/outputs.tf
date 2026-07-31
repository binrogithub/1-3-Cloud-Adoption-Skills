output "ec2_public_ip" {
  description = "Public IP of the EC2 instance"
  value       = aws_instance.web.public_ip
}

output "wordpress_url" {
  description = "WordPress URL"
  value       = "http://${aws_instance.web.public_ip}"
}

output "ssh_private_key" {
  description = "Private SSH key for EC2 access (save to file and chmod 600)"
  value       = tls_private_key.ssh.private_key_pem
  sensitive   = true
}

output "rds_endpoint" {
  description = "Endpoint of the RDS instance"
  value       = aws_db_instance.main.endpoint
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket"
  value       = aws_s3_bucket.main.bucket
}
