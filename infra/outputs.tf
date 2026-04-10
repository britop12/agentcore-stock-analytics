output "agentcore_endpoint" {
  description = "Agentcore Runtime invocation endpoint URL"
  value       = module.agentcore.agent_runtime_endpoint
}

output "ecr_repository_url" {
  description = "ECR repository URL for pushing Docker images"
  value       = module.ecr.repository_url
}

output "cognito_user_pool_id" {
  description = "Cognito User Pool ID"
  value       = module.cognito.user_pool_id
}

output "cognito_user_pool_client_id" {
  description = "Cognito User Pool App Client ID"
  value       = module.cognito.user_pool_client_id
}

output "knowledge_base_id" {
  description = "Bedrock Knowledge Base ID"
  value       = module.knowledge_base.knowledge_base_id
}
