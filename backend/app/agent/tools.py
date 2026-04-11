import dataclasses
import logging
from datetime import date

import yfinance as yf
from langchain_core.tools import tool

from app.models import HistoricalDataPoint, StockToolResult

logger = logging.getLogger(__name__)


def _get_realtime_price(ticker: str) -> tuple[float | None, list[str]]:
    """Try multiple yfinance methods to get the current price. Returns (price, errors)."""
    t = yf.Ticker(ticker)
    errors = []

    try:
        price = t.fast_info.last_price
        if price is not None:
            return float(price), errors
        errors.append("fast_info: last_price was None")
    except Exception as e:
        errors.append(f"fast_info: {type(e).__name__}: {e}")

    try:
        info = t.info
        price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
        if price is not None:
            return float(price), errors
        errors.append(f"info: no price keys found, keys={list(info.keys())[:10]}")
    except Exception as e:
        errors.append(f"info: {type(e).__name__}: {e}")

    try:
        hist = t.history(period="1d")
        if hist is not None and not hist.empty:
            return float(hist["Close"].iloc[-1]), errors
        errors.append(f"history(1d): empty={hist is None or hist.empty}")
    except Exception as e:
        errors.append(f"history: {type(e).__name__}: {e}")

    return None, errors


@tool
def retrieve_realtime_stock_price(ticker: str) -> dict:
    """Returns the current market price for the given ticker symbol."""
    try:
        price, errors = _get_realtime_price(ticker)

        if price is None:
            return dataclasses.asdict(
                StockToolResult(
                    ticker=ticker,
                    error=True,
                    code="TICKER_NOT_FOUND",
                    message=f"No price data found for ticker '{ticker}'. Debug: {'; '.join(errors)}",
                )
            )

        return dataclasses.asdict(
            StockToolResult(ticker=ticker, error=False, price=price)
        )

    except (ConnectionError, TimeoutError) as exc:
        logger.warning("Network error fetching realtime price for %s: %s", ticker, exc)
        return dataclasses.asdict(
            StockToolResult(
                ticker=ticker,
                error=True,
                code="DATA_SOURCE_UNAVAILABLE",
                message="The data source is currently unreachable.",
            )
        )
    except Exception as exc:
        exc_str = str(exc).lower()
        if "timeout" in exc_str or "connection" in exc_str:
            logger.warning("Network error fetching realtime price for %s: %s", ticker, exc)
            return dataclasses.asdict(
                StockToolResult(
                    ticker=ticker,
                    error=True,
                    code="DATA_SOURCE_UNAVAILABLE",
                    message="The data source is currently unreachable.",
                )
            )
        logger.warning("Unknown error fetching realtime price for %s: %s", ticker, exc)
        return dataclasses.asdict(
            StockToolResult(
                ticker=ticker,
                error=True,
                code="TICKER_NOT_FOUND",
                message=f"Ticker '{ticker}' was not found or returned no data.",
            )
        )


@tool
def retrieve_historical_stock_price(ticker: str, startDate: str, endDate: str) -> dict:
    """Returns daily closing prices for the given ticker between startDate and endDate (YYYY-MM-DD)."""
    # Validate date range
    try:
        start = date.fromisoformat(startDate)
        end = date.fromisoformat(endDate)
    except ValueError as exc:
        return dataclasses.asdict(
            StockToolResult(
                ticker=ticker,
                error=True,
                code="INVALID_DATE_RANGE",
                message=f"Invalid date format: {exc}",
            )
        )

    if start > end:
        return dataclasses.asdict(
            StockToolResult(
                ticker=ticker,
                error=True,
                code="INVALID_DATE_RANGE",
                message=f"startDate '{startDate}' must not be after endDate '{endDate}'.",
            )
        )

    try:
        t = yf.Ticker(ticker)
        df = t.history(start=startDate, end=endDate)

        # Fallback: try yf.download if history() returns empty
        if df is None or df.empty:
            df = yf.download(ticker, start=startDate, end=endDate, progress=False)

        if df is None or df.empty:
            return dataclasses.asdict(
                StockToolResult(
                    ticker=ticker,
                    error=True,
                    code="TICKER_NOT_FOUND",
                    message=f"No historical data found for ticker '{ticker}'.",
                )
            )

        # Build sorted list of HistoricalDataPoint ascending by date
        history = [
            dataclasses.asdict(
                HistoricalDataPoint(
                    date=idx.strftime("%Y-%m-%d"),
                    close=float(row["Close"]),
                )
            )
            for idx, row in sorted(df.iterrows(), key=lambda x: x[0])
        ]

        return dataclasses.asdict(
            StockToolResult(ticker=ticker, error=False, history=history)
        )

    except (ConnectionError, TimeoutError) as exc:
        logger.warning("Network error fetching historical data for %s: %s", ticker, exc)
        return dataclasses.asdict(
            StockToolResult(
                ticker=ticker,
                error=True,
                code="DATA_SOURCE_UNAVAILABLE",
                message="The data source is currently unreachable.",
            )
        )
    except Exception as exc:
        exc_str = str(exc).lower()
        if "timeout" in exc_str or "connection" in exc_str:
            logger.warning("Network error fetching historical data for %s: %s", ticker, exc)
            return dataclasses.asdict(
                StockToolResult(
                    ticker=ticker,
                    error=True,
                    code="DATA_SOURCE_UNAVAILABLE",
                    message="The data source is currently unreachable.",
                )
            )
        logger.warning("Unknown error fetching historical data for %s: %s", ticker, exc)
        return dataclasses.asdict(
            StockToolResult(
                ticker=ticker,
                error=True,
                code="TICKER_NOT_FOUND",
                message=f"Ticker '{ticker}' was not found or returned no data.",
            )
        )
