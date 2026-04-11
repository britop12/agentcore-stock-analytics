# agentcore-stock-analytics

A streaming AI agent API hosted on AWS Agentcore Runtime. Authenticated users send natural-language stock queries to a FastAPI endpoint. A LangGraph ReAct agent orchestrates reasoning over yfinance-backed stock tools and a Bedrock Knowledge Base of Amazon financial PDFs (backed by S3 Vectors), streaming partial results back via SSE.

---

## Prerequisites

- AWS CLI v2.34+ (must include `bedrock-agentcore-control` commands)
- Terraform 1.5+
- Docker Desktop (images must be built for `linux/arm64`)
- An AWS account with Bedrock model access enabled for Claude Haiku 4.5 and Titan Embed Text v2

### AWS IAM Permissions

The IAM principal running Terraform and CLI commands needs:

- `cognito-idp:*`, `ecr:*`, `iam:*`, `s3:*`, `s3vectors:*`
- `bedrock:*`, `bedrock-agent:*`, `bedrock-agentcore-control:*`
- `dynamodb:*`, `logs:*`

---

## Deployment

### 1. Create Terraform State Resources

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

aws s3api create-bucket \
  --bucket stock-agent-tf-state-$ACCOUNT_ID \
  --region us-east-1

aws dynamodb create-table \
  --table-name stock-agent-tf-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

### 2. Configure Terraform Backend

Edit `infra/backend.tf` and replace the placeholders:

```hcl
backend "s3" {
  bucket         = "stock-agent-tf-state-<YOUR_ACCOUNT_ID>"
  key            = "stock-agent/terraform.tfstate"
  region         = "us-east-1"
  dynamodb_table = "stock-agent-tf-lock"
  encrypt        = true
}
```

If using AWS SSO, add `profile = "<your-sso-profile>"` to both the backend block in `backend.tf` and the provider block in `main.tf`.

### 3. Provision Infrastructure (Terraform)

Terraform creates: Cognito, ECR, S3 Vectors, Bedrock Knowledge Base, IAM roles, and uploads/indexes the financial PDFs.

> **Note:** Terraform also attempts to create the Agentcore Runtime via a `null_resource`. This will fail on the first run because the ECR image doesn't exist yet. This is expected — the remaining resources (Cognito, ECR, KB, IAM) will be created successfully. The runtime is created manually in step 5 after pushing the Docker image.

```bash
cd infra
terraform init
terraform apply \
  -var="account_id=$(aws sts get-caller-identity --query Account --output text)" \
  -var="langfuse_public_key=<your-langfuse-public-key>" \
  -var="langfuse_secret_key=<your-langfuse-secret-key>" \
  -var="langfuse_host=<your-langfuse-host>"
```

Note the outputs — you'll need `ecr_repository_url`, `cognito_user_pool_id`, `cognito_user_pool_client_id`, and `knowledge_base_id`.

### 4. Build and Push the Docker Image

The ECR repository uses immutable tags, so use a versioned tag (not `latest`). Agentcore Runtime requires `arm64` images.

```bash
ECR_URL=$(terraform -chdir=infra output -raw ecr_repository_url)

aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin $ECR_URL

docker build --platform linux/arm64 -t $ECR_URL:v1.0.0 ./backend
docker push $ECR_URL:v1.0.0
```

### 5. Create the Agentcore Runtime

The Agentcore Runtime is created via AWS CLI because the Terraform provider doesn't fully support it yet:

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
KB_ID=$(terraform -chdir=infra output -raw knowledge_base_id)
POOL_ID=$(terraform -chdir=infra output -raw cognito_user_pool_id)
CLIENT_ID=$(terraform -chdir=infra output -raw cognito_user_pool_client_id)
ECR_URL=$(terraform -chdir=infra output -raw ecr_repository_url)

aws bedrock-agentcore-control create-agent-runtime \
  --region us-east-1 \
  --agent-runtime-name stock_agent_runtime \
  --agent-runtime-artifact "{\"containerConfiguration\":{\"containerUri\":\"$ECR_URL:v1.0.0\"}}" \
  --network-configuration '{"networkMode":"PUBLIC"}' \
  --role-arn "arn:aws:iam::${ACCOUNT_ID}:role/stock-agent-agentcore-execution-role" \
  --environment-variables "{\"AWS_REGION\":\"us-east-1\",\"BEDROCK_KB_ID\":\"$KB_ID\",\"COGNITO_APP_CLIENT_ID\":\"$CLIENT_ID\",\"COGNITO_REGION\":\"us-east-1\",\"COGNITO_USER_POOL_ID\":\"$POOL_ID\",\"LANGFUSE_HOST\":\"<your-langfuse-host>\",\"LANGFUSE_PUBLIC_KEY\":\"<your-langfuse-public-key>\",\"LANGFUSE_SECRET_KEY\":\"<your-langfuse-secret-key>\",\"MAX_ITERATIONS\":\"10\"}" \
  --authorizer-configuration "{\"customJWTAuthorizer\":{\"discoveryUrl\":\"https://cognito-idp.us-east-1.amazonaws.com/$POOL_ID/.well-known/openid-configuration\",\"allowedAudience\":[\"$CLIENT_ID\"]}}"
```

Wait for the runtime to reach `READY` status:

```bash
RUNTIME_ID=$(aws bedrock-agentcore-control list-agent-runtimes --region us-east-1 \
  --query 'agentRuntimes[?agentRuntimeName==`stock_agent_runtime`].agentRuntimeId' --output text)

aws bedrock-agentcore-control get-agent-runtime \
  --region us-east-1 --agent-runtime-id $RUNTIME_ID \
  --query 'status' --output text
```

### 6. Create a Cognito User

```bash
POOL_ID=$(terraform -chdir=infra output -raw cognito_user_pool_id)

aws cognito-idp admin-create-user \
  --user-pool-id $POOL_ID \
  --username testuser \
  --temporary-password 'Temp1234!' \
  --user-attributes Name=email,Value=test@example.com Name=email_verified,Value=true \
  --region us-east-1

aws cognito-idp admin-set-user-password \
  --user-pool-id $POOL_ID \
  --username testuser \
  --password 'MyPassword1!' \
  --permanent \
  --region us-east-1
```

### 7. Invoke the Agent

```bash
CLIENT_ID=$(terraform -chdir=infra output -raw cognito_user_pool_client_id)
RUNTIME_ID=$(aws bedrock-agentcore-control list-agent-runtimes --region us-east-1 \
  --query 'agentRuntimes[?agentRuntimeName==`stock_agent_runtime`].agentRuntimeId' --output text)

# Get JWT
JWT=$(aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id $CLIENT_ID \
  --auth-parameters USERNAME=testuser,PASSWORD='MyPassword1!' \
  --region us-east-1 \
  --query 'AuthenticationResult.IdToken' --output text)

# URL-encode the runtime ARN
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ARN="arn:aws:bedrock-agentcore:us-east-1:${ACCOUNT_ID}:runtime/${RUNTIME_ID}"
ENCODED_ARN=$(python3 -c "from urllib.parse import quote; print(quote('$ARN', safe=''))")
SESSION_ID=$(python3 -c "import uuid; print(uuid.uuid4())")

# Invoke (streaming SSE)
curl -s -X POST \
  "https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/${ENCODED_ARN}/invocations" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -H "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: $SESSION_ID" \
  -d '{"query": "What is the current price of AMZN?"}' \
  --no-buffer
```

The response streams as SSE events:

```
data: {"type": "token", "data": "The current price of AMZN is $203.28."}
data: {"type": "final", "data": ""}
```

---

## Architecture

- Authentication is handled by Agentcore's `customJWTAuthorizer` (validates Cognito JWTs before requests reach the container)
- The FastAPI container exposes `/invocations` (Agentcore's default path)
- The LangGraph ReAct agent has 3 tools: `retrieve_realtime_stock_price`, `retrieve_historical_stock_price`, and `retrieve_knowledge_base`
- Knowledge Base retrieval uses the Bedrock Retrieve API — all chunking, embedding, and indexing is managed by AWS
- Chunk text is stored in a supplemental S3 bucket to avoid S3 Vectors metadata size limits

---

## Environment Variables

Injected into the container by Agentcore Runtime:

| Variable | Description |
|---|---|
| `AWS_REGION` | AWS region (e.g. `us-east-1`) |
| `BEDROCK_KB_ID` | Bedrock Knowledge Base ID |
| `COGNITO_USER_POOL_ID` | Cognito User Pool ID for JWT validation |
| `COGNITO_APP_CLIENT_ID` | Cognito App Client ID |
| `COGNITO_REGION` | Cognito region |
| `MAX_ITERATIONS` | Max LangGraph reasoning iterations (default: `10`) |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key |
| `LANGFUSE_HOST` | Langfuse endpoint (default: `https://cloud.langfuse.com`) |

---

## Repository Structure

```
.
├── demo.ipynb            # Demo notebook (5 queries, auth, Langfuse traces)
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app
│   │   ├── models.py         # Request/response models
│   │   ├── routers/          # /invocations endpoint (SSE streaming)
│   │   └── agent/            # LangGraph ReAct agent, tools, KB retrieval
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
└── infra/
    ├── modules/
    │   ├── cognito/          # User Pool and App Client
    │   ├── ecr/              # Container registry
    │   ├── knowledge_base/   # Bedrock KB + S3 Vectors + S3 data/supplemental
    │   ├── agentcore/        # Runtime provisioner (null_resource)
    │   └── iam/              # Execution roles and policies
    ├── main.tf
    ├── backend.tf            # Remote state config (edit before deploy)
    ├── variables.tf
    └── outputs.tf
```
