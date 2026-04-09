"""
POST /invoke router — streams LangGraph agent responses as SSE.
"""

import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage

from app.agent.graph import build_graph
from app.models import InvokeRequest, StreamChunk

logger = logging.getLogger(__name__)

router = APIRouter()

# Compile the graph once at module load time.
graph = build_graph()


async def _event_stream(request: InvokeRequest):
    """Async generator that streams SSE chunks from the LangGraph agent."""
    initial_state = {
        "messages": [HumanMessage(content=request.query)],
        "iteration_count": 0,
        "query": request.query,
    }

    stream_gen = graph.astream(initial_state)
    try:
        async for chunk in stream_gen:
            # chunk is a dict of node_name → state updates from LangGraph
            for node_name, state_update in chunk.items():
                messages = state_update.get("messages", [])
                if not messages:
                    continue

                last_message = messages[-1]
                content = getattr(last_message, "content", "") or ""

                # Try to parse content as a StreamChunk JSON
                stream_chunk: StreamChunk
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict) and "type" in parsed:
                        stream_chunk = {"type": parsed["type"], "data": parsed.get("data", "")}
                    else:
                        stream_chunk = {"type": "token", "data": str(content)}
                except (json.JSONDecodeError, TypeError):
                    stream_chunk = {"type": "token", "data": str(content)}

                yield f"data: {json.dumps(stream_chunk)}\n\n"

        # Terminal event after stream ends normally
        terminal: StreamChunk = {"type": "final", "data": ""}
        yield f"data: {json.dumps(terminal)}\n\n"

    except Exception as exc:
        logger.error("Stream interrupted: %s", exc, exc_info=True)
        try:
            await stream_gen.aclose()
        except Exception:
            pass
        error_chunk: StreamChunk = {"type": "error", "data": str(exc)}
        yield f"data: {json.dumps(error_chunk)}\n\n"


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
