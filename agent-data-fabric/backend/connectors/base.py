"""Base connector abstract class."""

from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseConnector(ABC):
    """Abstract base class for all data connectors."""

    def __init__(self, name: str, config: dict, credentials: Optional[dict] = None):
        self.name = name
        self.config = config
        self.credentials = credentials or {}

    @abstractmethod
    async def test_connection(self) -> dict:
        """Test connectivity. Returns {"success": bool, "latency_ms": int}."""
        ...

    @abstractmethod
    async def discover_schema(self) -> dict:
        """Discover and return the schema of the data source."""
        ...

    @abstractmethod
    async def execute_query(self, query: str, params: Optional[dict] = None) -> list[dict]:
        """Execute a query and return results."""
        ...

    @abstractmethod
    async def write(self, resource: str, payload: dict) -> dict:
        """Write data to the connector."""
        ...

    async def close(self):
        """Clean up resources."""
        pass
