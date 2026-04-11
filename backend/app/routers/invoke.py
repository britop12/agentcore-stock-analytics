"""
POST /invoke router — streams LangGraph agent responses as SSE.
"""

import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage

from app.agent.graph import build_graph
from app.agent.observability import get_callback_handler
from app.models import InvokeRequest, StreamChunk

logger = logging.getLogger(__name__)

router = APIRouter()

# Compile the graph once at module load time.
graph = build_graph()


async def _event_stream(request: InvokeRequest):
    """Async generator that streams SSE chunks from the LangGraph agent.

    Uses astream_events filtered by LLM invocations to get true token-by-token
    streaming, plus tool call and tool result events.
    Reference: https://langchain-ai.github.io/langgraph/how-tos/streaming/#filter-by-llm-invocation
    """
    initial_state = {
        "messages": [HumanMessage(content=request.query)],
        "iteration_count": 0,
        "query": request.query,
    }

    callback = get_callback_handler()
    config = {"callbacks": [callback]} if callback else {}

    try:
        async for event in graph.astream_events(initial_state, config=config, version="v2"):
            kind = event.get("event", "")
            data = event.get("data", {})

            # Stream LLM tokens as they arrive
            if kind == "on_chat_model_stream":
                chunk = data.get("chunk")
                if chunk:
                    content = getattr(chunk, "content", "")
                    # Handle string content
                    if content and isinstance(content, str):
                        stream_chunk: StreamChunk = {"type": "token", "data": content}
                        yield f"data: {json.dumps(stream_chunk)}\n\n"
                    # Handle list content (Converse API returns list of dicts)
                    elif content and isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict):
                                text = block.get("text", "")
                            elif isinstance(block, str):
                                text = block
                            else:
                                text = str(block)
                            if text:
                                stream_chunk = {"type": "token", "data": text}
                                yield f"data: {json.dumps(stream_chunk)}\n\n"

            # Emit tool call events
            elif kind == "on_tool_start":
                tool_name = event.get("name", "")
                tool_input = data.get("input", {})
                stream_chunk = {"type": "tool_call", "data": json.dumps({"tool": tool_name, "input": tool_input})}
                yield f"data: {json.dumps(stream_chunk)}\n\n"

            # Emit tool result events
            elif kind == "on_tool_end":
                tool_name = event.get("name", "")
                output = data.get("output", "")
                output_str = str(output) if not isinstance(output, str) else output
                stream_chunk = {"type": "tool_result", "data": json.dumps({"tool": tool_name, "result": output_str[:500]})}
                yield f"data: {json.dumps(stream_chunk)}\n\n"

        # Terminal event after stream ends normally
        terminal: StreamChunk = {"type": "final", "data": ""}
        yield f"data: {json.dumps(terminal)}\n\n"

    except Exception as exc:
        logger.error("Stream interrupted: %s", exc, exc_info=True)
        error_chunk: StreamChunk = {"type": "error", "data": str(exc)}
        yield f"data: {json.dumps(error_chunk)}\n\n"


@router.post("/invocations")
@router.post("/invoke")
async def invoke(request: InvokeRequest) -> StreamingResponse:
    """
    Accept a user query and stream the agent's response as SSE.

    Returns a text/event-stream response where each event is a JSON-encoded
    StreamChunk. The final event has type "final".
    """
    return StreamingResponse(
        _event_stream(request),
        media_type="text/event-stream",
    )
