import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def get_callback_handler():
    """
    Create and return a Langfuse CallbackHandler for LangChain/LangGraph tracing.

    Returns a fresh CallbackHandler instance per call so each agent invocation
    gets its own trace. Returns None if Langfuse is unavailable or misconfigured.

    Returns:
        Optional[CallbackHandler]: A Langfuse callback handler, or None on failure.
    """
    try:
        from langfuse.callback import CallbackHandler

        public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
        secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
        host = os.environ.get("LANGFUSE_HOST")

        handler = CallbackHandler(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
        return handler
    except Exception as e:
        logging.warning("Langfuse observability unavailable: %s", e)
        return None
