"""FastAPI application — main entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.middleware.observability_middleware import ObservabilityMiddleware

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("adf")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name}...")
    logger.info(f"LLM backend: {'Azure OpenAI' if settings.use_azure_openai else 'Ollama'}")
    logger.info(f"Database: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
    yield
    logger.info(f"Shutting down {settings.app_name}...")


app = FastAPI(
    title=settings.app_name,
    description="Agentic Data Fabric — MCP-native universal data & action layer",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Observability
app.add_middleware(ObservabilityMiddleware)

# Register routers
from backend.api.health import router as health_router
from backend.api.auth import router as auth_router
from backend.api.connectors import router as connectors_router
from backend.api.mcp_servers import router as mcp_servers_router
from backend.api.mcp_registry import router as mcp_registry_router
from backend.api.tools import router as tools_router
from backend.api.sql_explorer import router as sql_router
from backend.api.chat import router as chat_router
from backend.api.rag import router as rag_router
from backend.api.observability import router as observability_router
from backend.api.capabilities import router as capabilities_router
from backend.api.ingestion import router as ingestion_router

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(connectors_router)
app.include_router(ingestion_router)
app.include_router(mcp_servers_router)
app.include_router(mcp_registry_router)
app.include_router(tools_router)
app.include_router(sql_router)
app.include_router(chat_router)
app.include_router(rag_router)
app.include_router(observability_router)
app.include_router(capabilities_router)
