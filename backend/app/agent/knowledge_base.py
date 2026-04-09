"""
Knowledge base backed by AWS S3 Vectors.

Downloads three Amazon financial PDFs at startup, chunks them into passages,
embeds each passage with Amazon Titan Embed, and upserts into an S3 Vectors
bucket.  Retrieval embeds the query and calls the S3 Vectors similarity-search
API, returning the top-k passage strings.
"""

import hashlib
import json
import logging
import os
import urllib.request
from typing import Optional

import boto3

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PDF text extraction — prefer pypdf, fall back to raw bytes
# ---------------------------------------------------------------------------

def _extract_text_from_pdf_bytes(data: bytes) -> str:
    try:
        import io
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(io.BytesIO(data))
        parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
        return "\n".join(parts)
    except Exception:
        # Fallback: decode bytes as latin-1 (lossless) and strip non-printable
        logger.warning("pypdf unavailable or failed; falling back to raw byte decoding")
        return data.decode("latin-1", errors="replace")


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split *text* into overlapping chunks of ~*chunk_size* characters."""
    chunks: list[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + chunk_size, length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == length:
            break
        start = end - overlap
    return chunks


# ---------------------------------------------------------------------------
# PDF URLs
# ---------------------------------------------------------------------------

PDF_URLS: list[str] = [
    "https://s2.q4cdn.com/299287126/files/doc_financials/2025/ar/Amazon-2024-Annual-Report.pdf",
    "https://s2.q4cdn.com/299287126/files/doc_financials/2025/q3/AMZN-Q3-2025-Earnings-Release.pdf",
    "https://s2.q4cdn.com/299287126/files/doc_financials/2025/q2/AMZN-Q2-2025-Earnings-Release.pdf",
]


# ---------------------------------------------------------------------------
# KnowledgeBase
# ---------------------------------------------------------------------------

class KnowledgeBase:
    """Manages indexing and retrieval of Amazon financial documents via S3 Vectors."""

    def __init__(self) -> None:
        self.bucket: str = os.environ.get("KB_S3_VECTORS_BUCKET", "")
        region: str = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))

        self._bedrock = boto3.client("bedrock-runtime", region_name=region)
        self._s3vectors = boto3.client("s3vectors", region_name=region)

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------

    def _embed(self, text: str) -> list[float]:
        """Embed *text* using Amazon Titan Embed Text v1."""
        body = json.dumps({"inputText": text})
        response = self._bedrock.invoke_model(
            modelId="amazon.titan-embed-text-v1",
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        result = json.loads(response["body"].read())
        return result["embedding"]

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_documents(self) -> None:
        """Download PDFs, chunk, embed, and upsert into S3 Vectors."""
        if not self.bucket:
            logger.warning("KB_S3_VECTORS_BUCKET is not set; skipping knowledge base indexing")
            return

        for url in PDF_URLS:
            logger.info("Downloading PDF: %s", url)
            try:
                with urllib.request.urlopen(url, timeout=60) as resp:  # noqa: S310
                    pdf_bytes = resp.read()
            except Exception as exc:
                logger.warning("Failed to download %s: %s", url, exc)
                continue

            text = _extract_text_from_pdf_bytes(pdf_bytes)
            chunks = _chunk_text(text)
            logger.info("Extracted %d chunks from %s", len(chunks), url)

            vectors = []
            for chunk in chunks:
                key = hashlib.sha256(chunk.encode()).hexdigest()
                try:
                    embedding = self._embed(chunk)
                except Exception as exc:
                    logger.warning("Failed to embed chunk (key=%s): %s", key, exc)
                    continue
                vectors.append(
                    {
                        "key": key,
                        "data": {"float32": embedding},
                        "metadata": {"text": chunk},
                    }
                )

            # Upsert in batches of 100 (S3 Vectors limit)
            batch_size = 100
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i : i + batch_size]
                try:
                    self._s3vectors.put_vectors(bucket=self.bucket, vectors=batch)
                    logger.info("Upserted batch %d-%d for %s", i, i + len(batch), url)
                except Exception as exc:
                    logger.warning("Failed to upsert batch %d-%d for %s: %s", i, i + len(batch), url, exc)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def retrieve(self, query: str, top_k: int = 5) -> list[str]:
        """Embed *query* and return the top-*top_k* passage strings from S3 Vectors.

        Returns an empty list when no relevant passages are found or when the
        bucket is not configured.
        """
        if not self.bucket:
            logger.warning("KB_S3_VECTORS_BUCKET is not set; returning empty results")
            return []

        try:
            query_embedding = self._embed(query)
        except Exception as exc:
            logger.warning("Failed to embed query '%s': %s", query, exc)
            return []

        try:
            response = self._s3vectors.query_vectors(
                bucket=self.bucket,
                queryVector={"float32": query_embedding},
                topK=top_k,
            )
        except Exception as exc:
            logger.warning("S3 Vectors query failed for query '%s': %s", query, exc)
            return []

        vectors = response.get("vectors", [])
        if not vectors:
            logger.warning("No relevant passages found for query: %s", query)
            return []

        passages: list[str] = []
        for vec in vectors:
            metadata = vec.get("metadata", {})
            text: Optional[str] = metadata.get("text")
            if text:
                passages.append(text)

        if not passages:
            logger.warning("No passage text found in S3 Vectors results for query: %s", query)

        return passages


# ---------------------------------------------------------------------------
# Module-level singleton and convenience function
# ---------------------------------------------------------------------------

knowledge_base = KnowledgeBase()


def retrieve(query: str) -> list[str]:
    """Top-level convenience function delegating to the module singleton."""
    return knowledge_base.retrieve(query)
