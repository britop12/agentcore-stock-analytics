"""FastAPI application entry point."""
import logging

from fastapi import FastAPI

from app.routers.invoke import router

logger = logging.getLogger(__name__)

app = FastAPI(title="AWS Stock Agent")

app.include_router(router)
