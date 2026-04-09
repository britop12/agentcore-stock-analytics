# Implementation Plan: aws-stock-agent

## Overview

Implement a streaming AI agent API on AWS Agentcore Runtime. The plan proceeds bottom-up: environment → data models → auth middleware → stock tools → knowledge base (S3 Vectors) → LangGraph agent → FastAPI app → Terraform infrastructure → tests → documentation.

## Tasks

- [x] 1. Set up Python environment and project structure
  - Create `backend/` and `infra/` top-level directories
  - Initialise Python virtual environment: `python -m venv .venv`
  - Create `backend/requirements.txt` with pinned dependencies: `fastapi`, `uvicorn`, `langgraph`, `langchain`, `langchain-aws`, `langfuse`, `yfinance`, `python-jose[cryptography]`, `boto3`, `hypothesis`, `pytest`, `pytest-asyncio`, `httpx`
  - Create `backend/pyproject.toml` (optional PEP 517 build metadata)
  - Create `backend/Dockerfile` based on `python:3.11-slim`, exposing port `8080`, running `uvicorn app.main:app --host 0.0.0.0 --port 8080`
  - Create `backend/.dockerignore` excluding `.venv`, `__pycache__`, `tests/`, `.env`
  - Create `backend/app/__init__.py`, `backend/app/routers/__init__.py`, `backend/app/middleware/__init__.py`, `backend/app/agent/__init__.py`
  - Create `backend/tests/unit/`, `backend/tests/property/`, `backend/tests/integration/` directories with `__init__.py` files
  - _Requirements: 2.2, 10.5_

- [x] 2. Define core data models
  - [x] 2.1 Implement data models in `backend/app/models.py`
    - `InvokeRequest(BaseModel)` with non-empty `query: str`
    - `StockToolResult` dataclass with `ticker`, `error`, `code`, `message`, `price`, `history` fields
    - `HistoricalDataPoint` dataclass with `date: str` (ISO 8601) and `close: float`
    - `AgentState(TypedDict)` with `messages`, `iteration_count`, `query`
    - `StreamChunk` typed dict with `type` literal and `data` fields
    - _Requirements: 2.1, 3.1, 4.1, 5.1, 7.1_

  - [ ]* 2.2 Write unit tests for data models
    - Test `InvokeRequest` rejects empty `query`
    - Test `StockToolResult` default field values
    - Test `HistoricalDataPoint` date format validation
    - _Requirements: 2.1, 4.1, 5.1_

- [x] 3. Implement Cognito JWT middleware
  - [x] 3.1 Implement `backend/app/middleware/auth.py`
    - Fetch JWKS from `https://cognito-idp.<region>.amazonaws.com/<pool_id>/.well-known/jwks.json` (cached)
    - Verify JWT signature, expiry, and audience using `python-jose`
    - Return HTTP 401 for missing, expired, tampered, or wrong-audience tokens
    - Attach decoded claims to `request.state.user` on success
    - _Requirements: 1.2, 1.3, 1.4_

  - [ ]* 3.2 Write unit tests for auth middleware
    - Generate local RSA key pair for test JWTs
    - Test valid token passes through
    - Test expired token returns 401
    - Test wrong audience returns 401
    - Test tampered signature returns 401
    - _Requirements: 1.2, 1.3, 1.4_

  - [ ]* 3.3 Write property test for JWT validation (Property 1 & 2)
    - **Property 1: Invalid JWT always yields 401**
    - Generate JWTs with tampered signatures, expired `exp`, wrong `aud` using Hypothesis `st.one_of`
    - Assert response status == 401 and agent is never called
    - **Property 2: Valid JWT always reaches the agent**
    - Generate well-formed JWTs signed with test RSA key
    - Assert response status != 401
    - `# Feature: aws-stock-agent, Property 1 & 2`
    - _Requirements: 1.2, 1.3, 1.4_

- [x] 4. Implement stock tools
  - [x] 4.1 Implement `backend/app/agent/tools.py`
    - `retrieve_realtime_stock_price(ticker: str) -> StockToolResult` decorated with `@tool`
    - `retrieve_historical_stock_price(ticker: str, start_date: str, end_date: str) -> StockToolResult` decorated with `@tool`
    - Validate `start_date <= end_date`; return `INVALID_DATE_RANGE` error otherwise
    - Catch yfinance `TickerNotFound` → return `TICKER_NOT_FOUND` error
    - Catch network/timeout errors → return `DATA_SOURCE_UNAVAILABLE` error
    - Return `StockToolResult` with populated `price` or `history` on success
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ]* 4.2 Write unit tests for stock tools
    - Mock `yfinance.Ticker` for valid ticker, unknown ticker, and unavailable API
    - Test `retrieve_realtime_stock_price` returns positive price on success
    - Test `retrieve_historical_stock_price` returns chronologically ordered records
    - Test `start_date > end_date` returns `INVALID_DATE_RANGE`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ]* 4.3 Write property tests for stock tools (Properties 3, 4, 5, 6)
    - **Property 3: Realtime tool round-trip** — `st.from_regex(r'[A-Z]{1,5}')` with mocked yfinance; assert `result.error == False` and `result.price > 0`
    - `# Feature: aws-stock-agent, Property 3`
    - **Property 4: Invalid ticker returns TICKER_NOT_FOUND** — arbitrary non-ticker strings; assert `result.error == True` and `result.code == "TICKER_NOT_FOUND"`
    - `# Feature: aws-stock-agent, Property 4`
    - **Property 5: start > end yields INVALID_DATE_RANGE** — generate date pairs where `start > end`; assert `result.error == True` and `result.code == "INVALID_DATE_RANGE"`
    - `# Feature: aws-stock-agent, Property 5`
    - **Property 6: Historical data ordering** — valid ticker + valid date range (mocked); assert returned dates are strictly ascending
    - `# Feature: aws-stock-agent, Property 6`
    - _Requirements: 4.2, 4.3, 5.2, 5.3, 5.4_

- [x] 5. Implement knowledge base with AWS S3 Vectors
  - [x] 5.1 Implement `backend/app/agent/knowledge_base.py`
    - Download the three Amazon financial PDFs at startup (URLs from Requirement 6.1) and chunk into passages
    - Use `boto3` S3 Vectors API (`s3vectors`) to create/upsert vector embeddings into the S3 Vectors bucket (bucket name read from env var `KB_S3_VECTORS_BUCKET`)
    - Implement `retrieve(query: str) -> list[str]` that embeds the query and calls the S3 Vectors similarity search API, returning top-k passage strings
    - Return empty list when no relevant passages found; log a warning
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [ ]* 5.2 Write unit tests for knowledge base
    - Mock `boto3` S3 Vectors client
    - Test `retrieve` returns passage list on successful search
    - Test `retrieve` returns empty list when S3 Vectors returns no results
    - _Requirements: 6.2, 6.3, 6.4_

- [x] 6. Implement Langfuse observability handler
  - [x] 6.1 Implement `backend/app/agent/observability.py`
    - Instantiate `langfuse.CallbackHandler` with credentials from env vars (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`)
    - Wrap all Langfuse calls in `try/except`; on exception emit `logging.warning(...)` and continue
    - Expose `get_callback_handler() -> CallbackHandler` for use by the agent graph
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [ ]* 6.2 Write property tests for Langfuse observability (Properties 8 & 9)
    - **Property 8: Langfuse trace completeness** — random queries with mocked Langfuse; assert trace contains input, all tool spans, KB spans, and final response
    - `# Feature: aws-stock-agent, Property 8`
    - **Property 9: Langfuse failure is non-blocking** — mock Langfuse to raise `ConnectionError`; assert agent completes and response is delivered
    - `# Feature: aws-stock-agent, Property 9`
    - _Requirements: 8.1, 8.2, 8.3, 8.5_

- [x] 7. Implement LangGraph ReAct agent graph
  - [x] 7.1 Implement `backend/app/agent/graph.py`
    - Define `AgentState` TypedDict (from `models.py`)
    - Instantiate `ChatBedrock(model_id="anthropic.claude-haiku-4-5", region_name=AWS_REGION, streaming=True)` from `langchain-aws`
    - Implement `reason` node: Claude Haiku 4.5 call that returns tool call or final answer
    - Implement `tool_executor` node: dispatches to `retrieve_realtime_stock_price`, `retrieve_historical_stock_price`, or `knowledge_base.retrieve`
    - Implement `terminal` node: emits final answer chunk and closes stream
    - Wire edges: `reason → tool_executor`, `reason → terminal`, `tool_executor → reason`
    - Add iteration guard: after `MAX_ITERATIONS` (env var, default 10) cycles, force-route to `terminal` with `{type: error, data: "max iterations reached"}`
    - Register Langfuse `CallbackHandler` from `observability.py`
    - Expose `build_graph() -> CompiledGraph`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 8.1, 8.2, 8.3_

  - [ ]* 7.2 Write unit tests for agent graph
    - Mock LLM and tool responses
    - Test routing from `reason` to `tool_executor` when tool call selected
    - Test routing from `reason` to `terminal` when final answer ready
    - Test iteration limit forces termination with error payload
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ]* 7.3 Write property tests for agent graph (Properties 7 & 10)
    - **Property 7: Iteration limit terminates the loop** — mock LLM to always return tool calls; assert agent terminates and last chunk is error terminal
    - `# Feature: aws-stock-agent, Property 7`
    - **Property 10: Stream completeness** — any valid query (mocked agent); assert exactly one terminal chunk exists and it is the last chunk
    - `# Feature: aws-stock-agent, Property 10`
    - _Requirements: 3.4, 3.5, 7.3, 7.4_

- [x] 8. Checkpoint — Ensure all unit and property tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement FastAPI application
  - [x] 9.1 Implement `backend/app/routers/invoke.py`
    - `POST /invoke` handler accepting `InvokeRequest`
    - Call `graph.astream(state)` and yield each chunk as SSE via `StreamingResponse`
    - Serialize each chunk as `StreamChunk` JSON
    - Send terminal SSE event when stream ends
    - On stream interruption: log and cancel the async generator
    - _Requirements: 2.1, 2.3, 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x] 9.2 Implement `backend/app/main.py`
    - Create FastAPI app instance
    - Register `AuthMiddleware` from `middleware/auth.py`
    - Mount `invoke` router
    - Add startup event to initialise knowledge base (index PDFs into S3 Vectors)
    - _Requirements: 1.2, 1.3, 1.4, 2.1, 2.2_

  - [ ]* 9.3 Write unit tests for invoke router
    - Mock agent graph; test 200 streaming response for valid request
    - Test 422 for missing `query` field
    - Test 401 propagation from auth middleware
    - Test SSE terminal event is last chunk
    - _Requirements: 2.1, 7.1, 7.3, 7.4_

- [x] 10. Provision Terraform infrastructure
  - [x] 10.1 Create `infra/backend.tf`
    - Configure S3 backend with `bucket`, `key`, `region`, `dynamodb_table` for state locking
    - _Requirements: 9.4_

  - [x] 10.2 Create `infra/modules/cognito/`
    - `main.tf`: Cognito User Pool, User Pool Client, domain
    - `variables.tf`, `outputs.tf`
    - _Requirements: 1.1, 1.5, 9.1, 9.2_

  - [x] 10.3 Create `infra/modules/iam/`
    - `main.tf`: shared IAM policies and role attachments (least-privilege)
    - Include permissions for ECR pull, S3 Vectors read/write, CloudWatch Logs write
    - Include `bedrock:InvokeModelWithResponseStream` for `anthropic.claude-haiku-4-5` model ARN
    - `variables.tf`, `outputs.tf`
    - _Requirements: 9.1, 9.2_

  - [x] 10.4 Create `infra/modules/ecr/`
    - `main.tf`: private ECR repository for the FastAPI container image
    - Enable image scanning on push and tag immutability
    - Output the repository URL for use by the `agentcore` module and CI/CD push step
    - `variables.tf`, `outputs.tf`
    - _Requirements: 2.2, 9.1, 9.2_

  - [x] 10.5 Create `infra/modules/agentcore/`
    - `main.tf`: Agentcore Runtime resource referencing the ECR image URI (from `ecr` module output)
    - Attach the IAM execution role (from `iam` module)
    - Inject env vars into the runtime: `COGNITO_REGION`, `COGNITO_USER_POOL_ID`, `COGNITO_APP_CLIENT_ID`, `KB_S3_VECTORS_BUCKET`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`, `MAX_ITERATIONS`, LLM API key
    - Configure container port `8080`
    - `variables.tf`, `outputs.tf` (expose the Agentcore Runtime endpoint URL)
    - _Requirements: 2.2, 2.4, 2.5, 9.1, 9.2_

  - [x] 10.6 Create S3 Vectors bucket Terraform module `infra/modules/s3_vectors/`
    - `main.tf`: S3 bucket configured for vector storage (S3 Vectors)
    - Expose bucket name as output; wire into `infra/main.tf` and pass as `KB_S3_VECTORS_BUCKET` env var to Agentcore Runtime
    - `variables.tf`, `outputs.tf`
    - _Requirements: 6.1, 9.1_

  - [x] 10.7 Create `infra/main.tf`, `infra/variables.tf`, `infra/outputs.tf`
    - Wire all modules together: `cognito` → `agentcore` (env vars), `ecr` → `agentcore` (image URI), `s3_vectors` → `agentcore` (bucket name), `iam` → `agentcore` (execution role)
    - Output the Agentcore Runtime endpoint URL and ECR repository URL
    - _Requirements: 9.1, 9.2, 9.3_

- [x] 11. Write integration tests
  - [ ]* 11.1 Write end-to-end integration test for `/invoke`
    - Real Cognito token (from env var `TEST_COGNITO_TOKEN`) + mocked yfinance
    - Assert 200 streaming response with at least one chunk and a terminal event
    - _Requirements: 2.1, 2.3, 7.1, 7.4_

  - [ ]* 11.2 Write Cognito token rejection integration tests
    - Assert expired token → 401
    - Assert tampered token → 401
    - _Requirements: 1.2, 1.3_

  - [ ]* 11.3 Write Terraform plan validation test
    - Run `terraform plan` in CI and assert no unexpected resource deletions
    - Assert IAM roles satisfy least-privilege policy
    - _Requirements: 9.1, 9.2, 9.3_

- [x] 12. Write README and deployment documentation
  - Implement `README.md` at repository root with:
    - Step-by-step deployment instructions:
      1. Create `.venv` and install dependencies
      2. Configure AWS credentials and prerequisites (S3 state bucket, DynamoDB table)
      3. Run `terraform apply` to provision Cognito, ECR, S3 Vectors, IAM, and Agentcore Runtime
      4. Build and push the Docker image to ECR: `docker build`, `docker tag`, `docker push`
      5. Register/update the Agentcore Runtime with the new ECR image URI
      6. Obtain a Cognito JWT and invoke the endpoint
    - All required environment variables (`COGNITO_REGION`, `COGNITO_USER_POOL_ID`, `COGNITO_APP_CLIENT_ID`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`, `KB_S3_VECTORS_BUCKET`, `MAX_ITERATIONS`, LLM API key)
    - AWS prerequisites (IAM permissions, S3 bucket for Terraform state, DynamoDB table)
    - Instructions for registering a Cognito user and obtaining a JWT token
    - Sample `curl` command invoking the Agentcore Runtime endpoint with a Bearer token and receiving a streamed response
  - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [x] 13. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests (Hypothesis, `@settings(max_examples=100)`) validate the 10 universal correctness properties from the design
- Unit tests validate specific examples and edge cases
- The knowledge base uses AWS S3 Vectors exclusively — no local FAISS or Chroma store
