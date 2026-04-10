"""
LangGraph ReAct agent graph for the aws-stock-agent.

Nodes:
  - reason: LLM call (Claude Haiku 4.5 via ChatBedrock) — decides next action
  - tool_executor: dispatches tool calls to stock tools or knowledge base
  - terminal: emits final answer / error and closes the stream

Edges:
  reason → tool_executor  (when tool call selected)
  reason → terminal       (when final answer ready or iteration limit hit)
  tool_executor → reason  (loop back for next reasoning step)
"""

import json
import logging
import os
from typing import Literal

from langchain_aws import ChatBedrock
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.graph import END, StateGraph

from app.agent.knowledge_base import retrieve_knowledge_base
from app.agent.observability import get_callback_handler
from app.agent.tools import retrieve_historical_stock_price, retrieve_realtime_stock_price
from app.models import AgentState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AWS_REGION: str = os.environ.get("AWS_REGION", "us-east-1")
MAX_ITERATIONS: int = int(os.environ.get("MAX_ITERATIONS", "10"))

# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

llm = ChatBedrock(
    model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
    region_name=AWS_REGION,
    streaming=True,
)

_tools = [retrieve_realtime_stock_price, retrieve_historical_stock_price, retrieve_knowledge_base]
llm_with_tools = llm.bind_tools(_tools)

# ---------------------------------------------------------------------------
# Tool dispatch map
# ---------------------------------------------------------------------------

_TOOL_MAP = {t.name: t for t in _tools}

# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def reason(state: AgentState) -> AgentState:
    """Call the LLM with current messages; increment iteration counter."""
    callback = get_callback_handler()
    kwargs = {"config": {"callbacks": [callback]}} if callback else {}

    response: AIMessage = llm_with_tools.invoke(state["messages"], **kwargs)

    return {
        **state,
        "messages": state["messages"] + [response],
        "iteration_count": state["iteration_count"] + 1,
    }


def tool_executor(state: AgentState) -> AgentState:
    """Execute all tool calls from the last AI message and append ToolMessages."""
    last_message: AIMessage = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", []) or []

    new_messages = []
    for tc in tool_calls:
        tool_name: str = tc["name"]
        tool_args: dict = tc["args"]
        tool_call_id: str = tc["id"]

        if tool_name in _TOOL_MAP:
            tool_fn = _TOOL_MAP[tool_name]
            result = tool_fn.invoke(tool_args)
            content = json.dumps(result) if not isinstance(result, str) else result
        else:
            logger.warning("Unknown tool requested: %s", tool_name)
            content = json.dumps({"error": True, "message": f"Unknown tool: {tool_name}"})

        new_messages.append(
            ToolMessage(content=content, tool_call_id=tool_call_id, name=tool_name)
        )

    return {
        **state,
        "messages": state["messages"] + new_messages,
    }


def terminal(state: AgentState) -> AgentState:
    """Emit the final answer or an error chunk and mark the stream as done."""
    last_message = state["messages"][-1] if state["messages"] else None

    if state["iteration_count"] >= MAX_ITERATIONS and (
        last_message is None or not isinstance(last_message, AIMessage) or getattr(last_message, "tool_calls", None)
    ):
        error_chunk = AIMessage(
            content=json.dumps({"type": "error", "data": "max iterations reached"})
        )
        return {
            **state,
            "messages": state["messages"] + [error_chunk],
        }

    return state


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def _route_after_reason(state: AgentState) -> Literal["tool_executor", "terminal"]:
    """Route to tool_executor if there are pending tool calls, else terminal."""
    if state["iteration_count"] >= MAX_ITERATIONS:
        return "terminal"

    last_message = state["messages"][-1] if state["messages"] else None
    if isinstance(last_message, AIMessage) and getattr(last_message, "tool_calls", None):
        return "tool_executor"

    return "terminal"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_graph():
    """Build and compile the LangGraph ReAct agent graph."""
    graph = StateGraph(AgentState)

    graph.add_node("reason", reason)
    graph.add_node("tool_executor", tool_executor)
    graph.add_node("terminal", terminal)

    graph.set_entry_point("reason")

    graph.add_conditional_edges(
        "reason",
        _route_after_reason,
        {
            "tool_executor": "tool_executor",
            "terminal": "terminal",
        },
    )

    graph.add_edge("tool_executor", "reason")
    graph.add_edge("terminal", END)

    return graph.compile()
