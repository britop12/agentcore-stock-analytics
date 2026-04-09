variable "app_name" {
  description = "Application name used to name the S3 Vectors bucket"
  type        = string
}

variable "region" {
  description = "AWS region where the bucket will be created"
  type        = string
  default     = "us-east-1"
}
