output "agent_runtime_id" {
  description = "The Agentcore Runtime ID"
  value       = trimspace(data.local_file.runtime_id.content)
}

output "agent_runtime_endpoint" {
  description = "The Agentcore Runtime invocation endpoint URL"
  # Endpoint pattern: https://bedrock-agentcore.<region>.amazonaws.com/runtimes/<runtime-id>/invocations
  value = "https://bedrock-agentcore.${var.region}.amazonaws.com/runtimes/${trimspace(data.local_file.runtime_id.content)}/invocations"
}
