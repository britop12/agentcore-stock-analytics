from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional, TypedDict

from pydantic import BaseModel, field_validator


class InvokeRequest(BaseModel):
    query: str

    @field_validator("query")
    @classmethod
    def query_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("query must not be empty")
        return v


@dataclass
class StockToolResult:
    ticker: str
    error: bool = False
    code: Optional[str] = None
    message: Optional[str] = None
    price: Optional[float] = None
    history: Optional[list] = None


@dataclass
class HistoricalDataPoint:
    date: str   # ISO 8601 YYYY-MM-DD
    close: float


# AgentState uses list[BaseMessage] from langchain_core.messages at runtime.
# Typed as plain list here to avoid a hard import dependency during testing.
class AgentState(TypedDict):
    messages: list  # list[BaseMessage]
    iteration_count: int
    query: str


class StreamChunk(TypedDict):
    type: Literal["token", "tool_call", "tool_result", "kb_result", "final", "error"]
    data: str
