output "knowledge_base_id" {
  description = "Bedrock Knowledge Base ID"
  value       = aws_bedrockagent_knowledge_base.this.id
}

output "data_source_id" {
  description = "Bedrock Knowledge Base data source ID"
  value       = aws_bedrockagent_data_source.this.data_source_id
}

output "vector_bucket_arn" {
  description = "ARN of the S3 Vectors vector bucket"
  value       = aws_s3vectors_vector_bucket.this.vector_bucket_arn
}
