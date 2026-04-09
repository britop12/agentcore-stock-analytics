import dataclasses
import logging
from datetime import date

import yfinance as yf
from langchain_core.tools import tool

from app.models import HistoricalDataPoint, StockToolResult

logger = logging.getLogger(__name__)


@tool
def retrieve_realtime_stock_price(ticker: str) -> dict:
    """Returns the current market price for the given ticker symbol."""
    try:
        info = yf.Ticker(ticker).fast_info
        price = info.last_price

        if price is None:
            return dataclasses.asdict(
                StockToolResult(
                    ticker=ticker,
                    error=True,
                    code="TICKER_NOT_FOUND",
                    message=f"No price data found for ticker '{ticker}'.",
                )
            )

        return dataclasses.asdict(
            StockToolResult(ticker=ticker, error=False, price=float(price))
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
def retrieve_historical_stock_price(ticker: str, start_date: str, end_date: str) -> dict:
    """Returns daily closing prices for the given ticker between start_date and end_date (YYYY-MM-DD)."""
    # Validate date range
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
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
                message=f"start_date '{start_date}' must not be after end_date '{end_date}'.",
            )
        )

    try:
        df = yf.Ticker(ticker).history(start=start_date, end=end_date)

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
