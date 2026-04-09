resource "aws_s3_bucket" "kb_vectors" {
  bucket = "${var.app_name}-kb-vectors"

  tags = {
    Name        = "${var.app_name}-kb-vectors"
    Application = var.app_name
  }
}

resource "aws_s3_bucket_versioning" "kb_vectors" {
  bucket = aws_s3_bucket.kb_vectors.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "kb_vectors" {
  bucket = aws_s3_bucket.kb_vectors.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "kb_vectors" {
  bucket = aws_s3_bucket.kb_vectors.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
