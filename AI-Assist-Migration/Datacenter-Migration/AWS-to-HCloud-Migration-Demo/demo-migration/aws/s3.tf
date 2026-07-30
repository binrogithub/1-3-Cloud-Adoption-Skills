resource "random_id" "bucket" {
  byte_length = 4
}

resource "aws_s3_bucket" "main" {
  bucket = "demo-bucket-${random_id.bucket.hex}"

  tags = {
    Name = "demo-bucket"
  }
}

resource "aws_s3_bucket_versioning" "main" {
  bucket = aws_s3_bucket.main.id

  versioning_configuration {
    status = "Enabled"
  }
}
