# agentcore-stock-analytics

A streaming AI agent API hosted on AWS Agentcore Runtime. Authenticated users send natural-language stock queries to a FastAPI `/invoke` endpoint. A LangGraph ReAct agent orchestrates reasoning over yfinance-backed stock tools and a knowledge base of Amazon financial PDFs, streaming partial results back via SSE.

---

## Prerequisites

### AWS IAM Permissions

The IAM principal running Terraform needs at minimum:

- `cognito-idp:*` — create and manage Cognito User Pools
- `ecr:*` — create and manage ECR repositories
- `iam:*` — create roles and attach policies
- `s3:*` — create S3 buckets (state bucket + S3 Vectors bucket)
- `dynamodb:*` — create the state-locking table
- `bedrock:*` — register Agentcore Runtime resources
- `logs:*` — create CloudWatch log groups

### S3 Bucket for Terraform State

Create an S3 bucket to store Terraform remote state:

```bash
aws s3api create-bucket \
  --bucket my-tf-state-bucket \
  --region us-east-1
```

Enable versioning (recommended):

```bash
aws s3api put-bucket-versioning \
  --bucket my-tf-state-bucket \
  --versioning-configuration Status=Enabled
```

### DynamoDB Table for State Locking

```bash
aws dynamodb create-table \
  --table-name my-tf-lock-table \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

---

## Deployment

### 1. Install Python Dependencies

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 2. Configure AWS Credentials

```bash
export AWS_ACCESS_KEY_ID=<your-access-key>
export AWS_SECRET_ACCESS_KEY=<your-secret-key>
export AWS_REGION=us-east-1
```

Or use a named profile:

```bash
export AWS_PROFILE=my-profile
```

### 3. Configure Terraform Backend

Edit `infra/backend.tf` and replace the placeholder values with your S3 bucket and DynamoDB table names:

```hcl
terraform {
  backend "s3" {
    bucket         = "my-tf-state-bucket"
    key            = "aws-stock-agent/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "my-tf-lock-table"
    encrypt        = true
  }
}
```

### 4. Provision Infrastructure

```bash
cd infra
terraform init
terraform apply \
  -var="account_id=$(aws sts get-caller-identity --query Account --output text)" \
  -var="langfuse_public_key=<your-langfuse-public-key>" \
  -var="langfuse_secret_key=<your-langfuse-secret-key>"
```

This provisions:
- Cognito User Pool and App Client
- Amazon ECR repository
- S3 Vectors bucket for the knowledge base
- IAM execution roles and policies
- Agentcore Runtime resource

After `apply` completes, note the outputs — you'll need the ECR URL and Agentcore endpoint.

### 5. Build and Push the Docker Image

```bash
# Authenticate Docker to ECR
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin <ecr_url>

# Build and push
docker build -t <ecr_url>:latest ./backend
docker push <ecr_url>:latest
```

Replace `<ecr_url>` with the ECR repository URL from the Terraform outputs.

### 6. Register a Cognito User and Obtain a JWT

Create a user in the Cognito User Pool:

```bash
aws cognito-idp admin-create-user \
  --user-pool-id <COGNITO_USER_POOL_ID> \
  --username testuser \
  --temporary-password "Temp1234!" \
  --region <COGNITO_REGION>
```

Set a permanent password (required before the user can authenticate):

```bash
aws cognito-idp admin-set-user-password \
  --user-pool-id <COGNITO_USER_POOL_ID> \
  --username testuser \
  --password "MyPassword1!" \
  --permanent \
  --region <COGNITO_REGION>
```

Obtain a JWT token using the App Client:

```bash
aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME=testuser,PASSWORD="MyPassword1!" \
  --client-id <COGNITO_APP_CLIENT_ID> \
  --region <COGNITO_REGION>
```

The `IdToken` (or `AccessToken`) in the response is your Bearer token.

### 7. Invoke the Endpoint

```bash
curl -X POST https://<agentcore_endpoint>/invoke \
  -H "Authorization: Bearer <your-jwt-token>" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the current price of AMZN?"}' \
  --no-buffer
```

The response streams back as server-sent events. Each chunk is a JSON object:

```json
{"type": "token", "data": "The current price of AMZN is..."}
{"type": "final", "data": "The current price of AMZN is $195.42."}
```

---

## Environment Variables

These variables are injected into the container by Agentcore Runtime (configured via Terraform). For local development, export them in your shell:

| Variable | Description |
|---|---|
| `AWS_REGION` | AWS region where resources are deployed (e.g. `us-east-1`) |
| `COGNITO_REGION` | AWS region of the Cognito User Pool |
| `COGNITO_USER_POOL_ID` | Cognito User Pool ID (e.g. `us-east-1_xxxxxxxxx`) |
| `COGNITO_APP_CLIENT_ID` | Cognito App Client ID |
| `KB_S3_VECTORS_BUCKET` | S3 Vectors bucket name used by the knowledge base |
| `MAX_ITERATIONS` | Maximum LangGraph reasoning iterations before forced termination (default: `10`) |
| `LANGFUSE_PUBLIC_KEY` | Langfuse project public key |
| `LANGFUSE_SECRET_KEY` | Langfuse project secret key |
| `LANGFUSE_HOST` | Langfuse endpoint (default: `https://cloud.langfuse.com`) |

### Local Development Example

```bash
export AWS_REGION=us-east-1
export COGNITO_REGION=us-east-1
export COGNITO_USER_POOL_ID=us-east-1_xxxxxxxxx
export COGNITO_APP_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
export KB_S3_VECTORS_BUCKET=aws-stock-agent-vectors
export MAX_ITERATIONS=10
export LANGFUSE_PUBLIC_KEY=pk-lf-...
export LANGFUSE_SECRET_KEY=sk-lf-...
export LANGFUSE_HOST=https://cloud.langfuse.com

cd backend
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

---

## Repository Structure

```
.
├── backend/                  # FastAPI application
│   ├── app/
│   │   ├── main.py           # App factory and middleware registration
│   │   ├── models.py         # Pydantic request/response models
│   │   ├── routers/          # Route handlers (invoke)
│   │   ├── middleware/       # JWT auth middleware
│   │   └── agent/            # LangGraph ReAct agent, tools, knowledge base
│   ├── tests/                # Unit, property, and integration tests
│   ├── Dockerfile
│   └── requirements.txt
└── infra/                    # Terraform infrastructure
    ├── modules/
    │   ├── cognito/          # Cognito User Pool and App Client
    │   ├── ecr/              # ECR repository
    │   ├── agentcore/        # Agentcore Runtime resource
    │   ├── iam/              # IAM roles and policies
    │   └── s3_vectors/       # S3 Vectors bucket
    ├── main.tf
    ├── backend.tf            # Remote state configuration
    ├── variables.tf
    └── outputs.tf
```
