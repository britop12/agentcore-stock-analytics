variable "app_name" {
  type        = string
  description = "Application name used for resource naming"
  default     = "aws-stock-agent"
}

variable "region" {
  type        = string
  description = "AWS region"
  default     = "us-east-1"
}

variable "account_id" {
  type        = string
  description = "AWS account ID"
}

variable "ecr_image_tag" {
  type        = string
  description = "Docker image tag to deploy"
  default     = "latest"
}

variable "langfuse_public_key" {
  type      = string
  sensitive = true
}

variable "langfuse_secret_key" {
  type      = string
  sensitive = true
}

variable "langfuse_host" {
  type    = string
  default = "https://cloud.langfuse.com"
}

variable "max_iterations" {
  type    = number
  default = 10
}
