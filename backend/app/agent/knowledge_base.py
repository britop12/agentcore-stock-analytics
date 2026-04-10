"""
Knowledge base retrieval via AWS Bedrock Knowledge Base API.

All chunking, embedding, and vector storage is managed by Bedrock.
This module only performs retrieval queries against the Knowledge Base.
"""

import logging
import os

import boto3
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_REGION = os.environ.get("AWS_REGION", "us-east-1")
_KB_ID = os.environ.get("BEDROCK_KB_ID", "")

_client = boto3.client("bedrock-agent-runtime", region_name=_REGION)


@tool
def retrieve_knowledge_base(query: str) -> list[str]:
    """Search the Amazon financial documents knowledge base and return relevant passages.

    Use this tool when the user asks about Amazon's financial reports,
    earnings releases, annual reports, revenue, profit, or any Amazon
    corporate financial data.
    """
    if not _KB_ID:
        logger.warning("BEDROCK_KB_ID is not set; returning empty results")
        return []

    try:
        response = _client.retrieve(
            knowledgeBaseId=_KB_ID,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {
                    "numberOfResults": 5,
                }
            },
        )
    except Exception as exc:
        logger.warning("Bedrock KB retrieve failed for query '%s': %s", query, exc)
        return []

    results = response.get("retrievalResults", [])
    passages = []
    for r in results:
        text = r.get("content", {}).get("text", "")
        if text:
            passages.append(text)

    if not passages:
        logger.info("No passages found for query: %s", query)

    return passages
