output "repository_url" {
  description = "ECR repository URL for use by the agentcore module and CI/CD push step"
  value       = aws_ecr_repository.this.repository_url
}

output "repository_arn" {
  description = "ECR repository ARN"
  value       = aws_ecr_repository.this.arn
}
