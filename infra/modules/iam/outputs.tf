output "execution_role_arn" {
  description = "ARN of the Agentcore execution IAM role"
  value       = aws_iam_role.agentcore_execution.arn
}

output "execution_role_name" {
  description = "Name of the Agentcore execution IAM role"
  value       = aws_iam_role.agentcore_execution.name
}
