# Requirements Document

## Introduction

An AI agent solution hosted on AWS that exposes a FastAPI endpoint via AWS Agentcore Runtime. Users authenticate through AWS Cognito and can query real-time or historical stock prices. The agent uses a LangGraph ReAct-type orchestration loop, retrieves financial documents from a knowledge base, and streams all responses back to the caller. Observability is provided via Langfuse cloud (free tier). Infrastructure is provisioned with Terraform.

## Glossary

- **Agent**: The LangGraph ReAct-type AI agent that orchestrates tool calls and knowledge base retrieval to answer user queries.
- **Agentcore_Runtime**: The AWS Agentcore runtime that hosts the FastAPI application and exposes it as a managed endpoint.
- **API**: The FastAPI application that receives authenticated HTTP requests and returns streamed responses.
- **Cognito**: The AWS Cognito User Pool used to authenticate and authorize inbound user requests.
- **Knowledge_Base**: The document retrieval store containing the three Amazon financial PDF documents.
- **LangGraph**: The agent orchestration framework used to implement the ReAct agent loop.
- **Langfuse**: The cloud-based observability platform (free tier) used to trace and monitor agent executions.
- **Stock_Tool**: Either of the two yfinance-backed tools (`retrieve_realtime_stock_price` or `retrieve_historical_stock_price`) available to the Agent.
- **Terraform**: The infrastructure-as-code tool used to provision all AWS resources.
- **User**: A human or system caller that sends authenticated queries to the API endpoint.

---

## Requirements

### Requirement 1: User Authentication and Authorization

**User Story:** As a user, I want to authenticate via AWS Cognito before querying the agent, so that only authorized callers can access the endpoint.

#### Acceptance Criteria

1. THE Cognito SHALL provide a User Pool that issues JWT tokens for registered users.
2. WHEN a request arrives at the API without a valid Cognito JWT token, THE API SHALL return an HTTP 401 response.
3. WHEN a request arrives at the API with an expired Cognito JWT token, THE API SHALL return an HTTP 401 response.
4. WHEN a request arrives at the API with a valid Cognito JWT token, THE API SHALL forward the request to the Agent for processing.
5. THE Terraform SHALL provision the Cognito User Pool, User Pool Client, and all associated IAM policies required for token validation.

---

### Requirement 2: FastAPI Endpoint Hosted on Agentcore Runtime

**User Story:** As a user, I want a stable HTTP endpoint to send stock queries to, so that I can interact with the agent programmatically.

#### Acceptance Criteria

1. THE API SHALL expose a POST endpoint at `/invoke` that accepts a JSON body containing a `query` string field.
2. THE Agentcore_Runtime SHALL host the FastAPI application as a managed AWS service.
3. WHEN the Agentcore_Runtime receives a valid invocation request, THE API SHALL begin streaming the Agent response to the caller.
4. THE Terraform SHALL provision the Agentcore_Runtime configuration and any required execution roles.
5. IF the Agentcore_Runtime fails to start the FastAPI application, THEN THE Agentcore_Runtime SHALL emit an error event to the configured log destination.

---

### Requirement 3: LangGraph ReAct Agent Orchestration

**User Story:** As a user, I want the agent to reason over my query and decide which tools or documents to use, so that I receive accurate and contextual answers.

#### Acceptance Criteria

1. THE Agent SHALL implement a ReAct-type reasoning loop using LangGraph.
2. WHEN the Agent receives a user query, THE Agent SHALL determine whether to invoke a Stock_Tool, query the Knowledge_Base, or respond directly.
3. WHILE the Agent is executing a reasoning step, THE Agent SHALL not return a final response until the reasoning loop reaches a terminal state.
4. THE LangGraph SHALL be configured with a maximum iteration limit to prevent infinite reasoning loops.
5. IF the Agent exceeds the maximum iteration limit, THEN THE Agent SHALL return a structured error message indicating the limit was reached.

---

### Requirement 4: Real-Time Stock Price Retrieval Tool

**User Story:** As a user, I want to query the current price of a stock, so that I can get up-to-date market information.

#### Acceptance Criteria

1. THE Stock_Tool `retrieve_realtime_stock_price` SHALL accept a ticker symbol string as input.
2. WHEN `retrieve_realtime_stock_price` is called with a valid ticker symbol, THE Stock_Tool SHALL return the current market price using the yfinance API.
3. IF `retrieve_realtime_stock_price` is called with an unrecognized ticker symbol, THEN THE Stock_Tool SHALL return a structured error message indicating the ticker was not found.
4. IF the yfinance API is unavailable, THEN THE Stock_Tool SHALL return a structured error message indicating the data source is unreachable.

---

### Requirement 5: Historical Stock Price Retrieval Tool

**User Story:** As a user, I want to query historical stock prices for a given date range, so that I can analyze past market performance.

#### Acceptance Criteria

1. THE Stock_Tool `retrieve_historical_stock_price` SHALL accept a ticker symbol string, a start date, and an end date as inputs.
2. WHEN `retrieve_historical_stock_price` is called with a valid ticker symbol and date range, THE Stock_Tool SHALL return the daily closing prices for that range using the yfinance API.
3. IF `retrieve_historical_stock_price` is called with a start date that is after the end date, THEN THE Stock_Tool SHALL return a structured error message indicating the invalid date range.
4. IF `retrieve_historical_stock_price` is called with an unrecognized ticker symbol, THEN THE Stock_Tool SHALL return a structured error message indicating the ticker was not found.
5. IF the yfinance API is unavailable, THEN THE Stock_Tool SHALL return a structured error message indicating the data source is unreachable.

---

### Requirement 6: Financial Document Knowledge Base

**User Story:** As a user, I want the agent to answer questions grounded in Amazon's official financial reports, so that I receive accurate fundamental analysis.

#### Acceptance Criteria

1. THE Knowledge_Base SHALL index the following three documents:
   - Amazon 2024 Annual Report (https://s2.q4cdn.com/299287126/files/doc_financials/2025/ar/Amazon-2024-Annual-Report.pdf)
   - AMZN Q3 2025 Earnings Release (https://s2.q4cdn.com/299287126/files/doc_financials/2025/q3/AMZN-Q3-2025-Earnings-Release.pdf)
   - AMZN Q2 2025 Earnings Release (https://s2.q4cdn.com/299287126/files/doc_financials/2025/q2/AMZN-Q2-2025-Earnings-Release.pdf)
2. WHEN the Agent determines that a user query requires document context, THE Agent SHALL retrieve relevant passages from the Knowledge_Base before generating a response.
3. WHEN the Knowledge_Base returns retrieved passages, THE Agent SHALL include those passages as context in the final response generation step.
4. IF the Knowledge_Base returns no relevant passages for a query, THEN THE Agent SHALL proceed to answer using available tool results or general knowledge, and SHALL indicate that no document context was found.

---

### Requirement 7: Streaming Event Responses

**User Story:** As a user, I want to receive streamed responses from the agent, so that I see partial results as they are generated rather than waiting for the full response.

#### Acceptance Criteria

1. THE API SHALL stream the Agent's response using server-sent events or chunked HTTP transfer encoding.
2. THE Agent SHALL produce streamed output via LangGraph's `.astream()` method.
3. WHEN the Agent emits a streamed token or event chunk, THE API SHALL forward that chunk to the caller without buffering the full response.
4. WHEN the Agent completes the reasoning loop, THE API SHALL send a terminal event indicating the stream has ended.
5. IF the streaming connection is interrupted before the Agent completes, THEN THE API SHALL log the interruption and release all associated resources.

---

### Requirement 8: Observability via Langfuse

**User Story:** As a developer, I want all agent executions to be traced in Langfuse, so that I can monitor performance, debug failures, and analyze usage patterns.

#### Acceptance Criteria

1. THE Agent SHALL emit a trace to Langfuse for every invocation, including the input query, tool calls made, and final response.
2. WHEN a Stock_Tool is invoked during an Agent run, THE Agent SHALL record the tool name, input arguments, and output as a span within the active Langfuse trace.
3. WHEN the Knowledge_Base is queried during an Agent run, THE Agent SHALL record the query and retrieved passages as a span within the active Langfuse trace.
4. THE Agent SHALL use the Langfuse cloud free tier endpoint for all trace submissions.
5. IF the Langfuse endpoint is unreachable, THEN THE Agent SHALL log a warning and continue processing without failing the user request.

---

### Requirement 9: Terraform Infrastructure Provisioning

**User Story:** As a developer, I want all AWS infrastructure defined in Terraform, so that the environment can be reproduced and version-controlled reliably.

#### Acceptance Criteria

1. THE Terraform SHALL provision all AWS resources required by the solution, including Cognito, Agentcore_Runtime, IAM roles, and any supporting services.
2. THE Terraform SHALL be organized into logical modules: one for authentication (Cognito), one for the agent runtime (Agentcore_Runtime), and one for shared IAM resources.
3. WHEN `terraform apply` is executed against a clean AWS account with appropriate permissions, THE Terraform SHALL provision all resources without manual intervention.
4. THE Terraform SHALL store remote state in an S3 backend with DynamoDB state locking.
5. IF a Terraform resource fails to provision, THEN THE Terraform SHALL output a descriptive error message identifying the failed resource and the reason for failure.

---

### Requirement 10: Repository Structure and Deployment Documentation

**User Story:** As a developer, I want a clear README with deployment instructions, so that I can set up the solution in a new environment without prior knowledge of the codebase.

#### Acceptance Criteria

1. THE repository SHALL contain a `README.md` at the root level with step-by-step deployment instructions.
2. THE `README.md` SHALL document all required environment variables and AWS prerequisites needed before running `terraform apply`.
3. THE `README.md` SHALL include instructions for registering a Cognito user and obtaining a JWT token for testing the endpoint.
4. THE `README.md` SHALL include a sample `curl` command demonstrating how to invoke the `/invoke` endpoint with a valid token and receive a streamed response.
5. THE repository SHALL separate source code into a `backend/` directory and infrastructure code into an `infra/` directory.
