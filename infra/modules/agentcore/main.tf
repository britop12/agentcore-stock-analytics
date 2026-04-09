locals {
  runtime_name    = "${var.app_name}-runtime"
  runtime_id_file = "${path.module}/runtime_id.txt"
}

# Create the Agentcore Runtime via AWS CLI (aws_bedrock_agentcore_runtime is not yet GA in the Terraform provider)
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

      RUNTIME_ID=$(aws bedrock-agentcore create-agent-runtime \
        --region "${var.region}" \
        --agent-runtime-name "${local.runtime_name}" \
        --agent-runtime-artifact '{"containerConfiguration":{"containerUri":"${var.ecr_image_uri}"}}' \
        --network-configuration '{"networkMode":"PUBLIC"}' \
        --execution-role-arn "${var.execution_role_arn}" \
        --environment-variables '{
          "COGNITO_REGION":"${var.cognito_region}",
          "COGNITO_USER_POOL_ID":"${var.cognito_user_pool_id}",
          "COGNITO_APP_CLIENT_ID":"${var.cognito_app_client_id}",
          "KB_S3_VECTORS_BUCKET":"${var.kb_s3_vectors_bucket}",
          "LANGFUSE_PUBLIC_KEY":"${var.langfuse_public_key}",
          "LANGFUSE_SECRET_KEY":"${var.langfuse_secret_key}",
          "LANGFUSE_HOST":"${var.langfuse_host}",
          "MAX_ITERATIONS":"${var.max_iterations}",
          "AWS_REGION":"${var.region}"
        }' \
        --query 'agentRuntimeId' \
        --output text 2>/dev/null || \
      aws bedrock-agentcore update-agent-runtime \
        --region "${var.region}" \
        --agent-runtime-name "${local.runtime_name}" \
        --agent-runtime-artifact '{"containerConfiguration":{"containerUri":"${var.ecr_image_uri}"}}' \
        --execution-role-arn "${var.execution_role_arn}" \
        --environment-variables '{
          "COGNITO_REGION":"${var.cognito_region}",
          "COGNITO_USER_POOL_ID":"${var.cognito_user_pool_id}",
          "COGNITO_APP_CLIENT_ID":"${var.cognito_app_client_id}",
          "KB_S3_VECTORS_BUCKET":"${var.kb_s3_vectors_bucket}",
          "LANGFUSE_PUBLIC_KEY":"${var.langfuse_public_key}",
          "LANGFUSE_SECRET_KEY":"${var.langfuse_secret_key}",
          "LANGFUSE_HOST":"${var.langfuse_host}",
          "MAX_ITERATIONS":"${var.max_iterations}",
          "AWS_REGION":"${var.region}"
        }' \
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
        aws bedrock-agentcore delete-agent-runtime \
          --region "${self.triggers.region}" \
          --agent-runtime-id "$RUNTIME_ID" || true
        rm -f "$RUNTIME_ID_FILE"
      fi
    EOT
    interpreter = ["bash", "-c"]
  }
}

# Read back the runtime ID written by the provisioner
data "local_file" "runtime_id" {
  filename   = local.runtime_id_file
  depends_on = [null_resource.agentcore_runtime]
}
