import pytest
from pydantic import ValidationError

from app.models import (
    AgentState,
    HistoricalDataPoint,
    InvokeRequest,
    StockToolResult,
    StreamChunk,
)


class TestInvokeRequest:
    def test_valid_query(self):
        req = InvokeRequest(query="What is AMZN price?")
        assert req.query == "What is AMZN price?"

    def test_empty_string_rejected(self):
        with pytest.raises(ValidationError):
            InvokeRequest(query="")

    def test_whitespace_only_rejected(self):
        with pytest.raises(ValidationError):
            InvokeRequest(query="   ")

    def test_missing_query_rejected(self):
        with pytest.raises(ValidationError):
            InvokeRequest()


class TestStockToolResult:
    def test_minimal_construction(self):
        result = StockToolResult(ticker="AMZN")
        assert result.ticker == "AMZN"
        assert result.error is False
        assert result.code is None
        assert result.message is None
        assert result.price is None
        assert result.history is None

    def test_success_with_price(self):
        result = StockToolResult(ticker="AMZN", price=195.5)
        assert result.price == 195.5
        assert result.error is False

    def test_error_result(self):
        result = StockToolResult(
            ticker="INVALID",
            error=True,
            code="TICKER_NOT_FOUND",
            message="Ticker not found",
        )
        assert result.error is True
        assert result.code == "TICKER_NOT_FOUND"

    def test_history_field(self):
        history = [{"date": "2024-01-01", "close": 150.0}]
        result = StockToolResult(ticker="AMZN", history=history)
        assert result.history == history


class TestHistoricalDataPoint:
    def test_construction(self):
        point = HistoricalDataPoint(date="2024-01-15", close=153.42)
        assert point.date == "2024-01-15"
        assert point.close == 153.42


class TestAgentState:
    def test_construction(self):
        state: AgentState = {
            "messages": [],
            "iteration_count": 0,
            "query": "test query",
        }
        assert state["messages"] == []
        assert state["iteration_count"] == 0
        assert state["query"] == "test query"


class TestStreamChunk:
    def test_token_chunk(self):
        chunk: StreamChunk = {"type": "token", "data": "hello"}
        assert chunk["type"] == "token"
        assert chunk["data"] == "hello"

    def test_all_valid_types(self):
        valid_types = ["token", "tool_call", "tool_result", "kb_result", "final", "error"]
        for t in valid_types:
            chunk: StreamChunk = {"type": t, "data": "payload"}
            assert chunk["type"] == t
