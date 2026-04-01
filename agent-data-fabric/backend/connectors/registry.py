"""Connector registry — singleton managing active connectors."""

from typing import Optional
from backend.connectors.base import BaseConnector


class ConnectorRegistry:
    _instance: Optional["ConnectorRegistry"] = None
    _connectors: dict[str, BaseConnector] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._connectors = {}
        return cls._instance

    def register(self, name: str, connector: BaseConnector):
        self._connectors[name] = connector

    def unregister(self, name: str):
        self._connectors.pop(name, None)

    def get(self, name: str) -> Optional[BaseConnector]:
        return self._connectors.get(name)

    def list_all(self) -> dict[str, BaseConnector]:
        return dict(self._connectors)

    def is_registered(self, name: str) -> bool:
        return name in self._connectors


connector_registry = ConnectorRegistry()
