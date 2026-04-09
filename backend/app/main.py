"""FastAPI application entry point."""
import logging

from fastapi import FastAPI

from app.middleware.auth import AuthMiddleware
from app.routers.invoke import router
from app.agent.knowledge_base import knowledge_base

logger = logging.getLogger(__name__)

app = FastAPI(title="AWS Stock Agent")

app.add_middleware(AuthMiddleware)
app.include_router(router)


@app.on_event("startup")
async def startup_event() -> None:
    """Index financial documents into S3 Vectors on startup."""
    try:
        knowledge_base.index_documents()
    except Exception as exc:
        logger.warning("Knowledge base indexing failed during startup: %s", exc)
