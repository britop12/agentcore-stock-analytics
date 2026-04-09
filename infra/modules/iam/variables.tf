variable "app_name" {
  type        = string
  description = "Application name used for resource naming"
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

variable "ecr_repository_arn" {
  type        = string
  description = "ECR repository ARN"
}

variable "s3_vectors_bucket_arn" {
  type        = string
  description = "S3 Vectors bucket ARN"
}
