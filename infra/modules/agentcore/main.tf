locals {
  runtime_name    = replace("${var.app_name}_runtime", "-", "_")
  runtime_id_file = "${path.module}/runtime_id.txt"
  env_vars = jsonencode({
    "COGNITO_REGION"        = var.cognito_region
    "COGNITO_USER_POOL_ID"  = var.cognito_user_pool_id
    "COGNITO_APP_CLIENT_ID" = var.cognito_app_client_id
    "BEDROCK_KB_ID"         = var.bedrock_kb_id
    "LANGFUSE_PUBLIC_KEY"   = var.langfuse_public_key
    "LANGFUSE_SECRET_KEY"   = var.langfuse_secret_key
    "LANGFUSE_HOST"         = var.langfuse_host
    "MAX_ITERATIONS"        = tostring(var.max_iterations)
    "AWS_REGION"            = var.region
  })
}

resource "null_resource" "agentcore_runtime" {
  triggers = {
    image_uri          = var.ecr_image_uri
    execution_role_arn = var.execution_role_arn
    runtime_name       = local.runtime_name
    region             = var.region
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e

      RUNTIME_ID=$(aws bedrock-agentcore-control create-agent-runtime \
        --region "${var.region}" \
        --agent-runtime-name "${local.runtime_name}" \
        --agent-runtime-artifact '{"containerConfiguration":{"containerUri":"${var.ecr_image_uri}"}}' \
        --network-configuration '{"networkMode":"PUBLIC"}' \
        --role-arn "${var.execution_role_arn}" \
        --environment-variables '${local.env_vars}' \
        --query 'agentRuntimeId' \
        --output text 2>/dev/null || \
      aws bedrock-agentcore-control update-agent-runtime \
        --region "${var.region}" \
        --agent-runtime-id "$(cat ${local.runtime_id_file} 2>/dev/null || echo '')" \
        --agent-runtime-artifact '{"containerConfiguration":{"containerUri":"${var.ecr_image_uri}"}}' \
        --environment-variables '${local.env_vars}' \
        --query 'agentRuntimeId' \
        --output text)

      echo "$RUNTIME_ID" > "${local.runtime_id_file}"
    EOT
    interpreter = ["bash", "-c"]
  }

  provisioner "local-exec" {
    when    = destroy
    command = <<-EOT
      RUNTIME_ID_FILE="${path.module}/runtime_id.txt"
      if [ -f "$RUNTIME_ID_FILE" ]; then
        RUNTIME_ID=$(cat "$RUNTIME_ID_FILE")
        aws bedrock-agentcore-control delete-agent-runtime \
          --region "${self.triggers.region}" \
          --agent-runtime-id "$RUNTIME_ID" || true
        rm -f "$RUNTIME_ID_FILE"
      fi
    EOT
    interpreter = ["bash", "-c"]
  }
}

data "local_file" "runtime_id" {
  filename   = local.runtime_id_file
  depends_on = [null_resource.agentcore_runtime]
}
