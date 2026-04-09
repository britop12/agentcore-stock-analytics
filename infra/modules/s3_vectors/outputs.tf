output "bucket_name" {
  description = "Name of the S3 Vectors bucket"
  value       = aws_s3_bucket.kb_vectors.bucket
}

output "bucket_arn" {
  description = "ARN of the S3 Vectors bucket"
  value       = aws_s3_bucket.kb_vectors.arn
}
