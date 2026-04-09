variable "app_name" {
  type        = string
  description = "Application name used for resource naming"
}

variable "region" {
  type        = string
  description = "AWS region"
  default     = "us-east-1"
}

variable "ecr_image_uri" {
  type        = string
  description = "Full ECR image URI including tag"
}

variable "execution_role_arn" {
  type        = string
  description = "ARN of the IAM execution role for the Agentcore Runtime"
}

variable "cognito_region" {
  type        = string
  description = "AWS region where the Cognito User Pool is deployed"
}

variable "cognito_user_pool_id" {
  type        = string
  description = "Cognito User Pool ID"
}

variable "cognito_app_client_id" {
  type        = string
  description = "Cognito App Client ID"
}

variable "kb_s3_vectors_bucket" {
  type        = string
  description = "S3 Vectors bucket name used by the knowledge base"
}

variable "langfuse_public_key" {
  type        = string
  description = "Langfuse public API key"
  sensitive   = true
}

variable "langfuse_secret_key" {
  type        = string
  description = "Langfuse secret API key"
  sensitive   = true
}

variable "langfuse_host" {
  type        = string
  description = "Langfuse host endpoint"
  default     = "https://cloud.langfuse.com"
}

variable "max_iterations" {
  type        = number
  description = "Maximum number of agent reasoning iterations before forced termination"
  default     = 10
}
