provider "aws" {
  region = var.region
}

module "cognito" {
  source   = "./modules/cognito"
  app_name = var.app_name
  region   = var.region
}

module "ecr" {
  source   = "./modules/ecr"
  app_name = var.app_name
}

module "knowledge_base" {
  source     = "./modules/knowledge_base"
  app_name   = var.app_name
  region     = var.region
  account_id = var.account_id
}

module "iam" {
  source             = "./modules/iam"
  app_name           = var.app_name
  region             = var.region
  account_id         = var.account_id
  ecr_repository_arn = module.ecr.repository_arn
  knowledge_base_id  = module.knowledge_base.knowledge_base_id
}

module "agentcore" {
  source   = "./modules/agentcore"
  app_name = var.app_name
  region   = var.region

  ecr_image_uri      = "${module.ecr.repository_url}:${var.ecr_image_tag}"
  execution_role_arn = module.iam.execution_role_arn

  cognito_region        = module.cognito.region
  cognito_user_pool_id  = module.cognito.user_pool_id
  cognito_app_client_id = module.cognito.user_pool_client_id

  bedrock_kb_id = module.knowledge_base.knowledge_base_id

  langfuse_public_key = var.langfuse_public_key
  langfuse_secret_key = var.langfuse_secret_key
  langfuse_host       = var.langfuse_host
  max_iterations      = var.max_iterations
}
