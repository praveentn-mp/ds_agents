"""Azure Blob Storage connector."""

import os
import time
from typing import Optional
from backend.connectors.base import BaseConnector


class AzureBlobConnector(BaseConnector):
    def __init__(self, name: str, config: dict, credentials: Optional[dict] = None):
        super().__init__(name, config, credentials)
        self._client = None

    @staticmethod
    def _get_ssl_ca_path():
        """Return certifi CA bundle path for SSL verification (fixes macOS cert issues)."""
        try:
            import certifi
            return certifi.where()
        except ImportError:
            return True  # Fall back to default SSL verification

    def _get_client(self):
        if self._client is None:
            try:
                from azure.storage.blob.aio import BlobServiceClient
            except ImportError:
                raise RuntimeError("azure-storage-blob package is required. Install: pip install azure-storage-blob")

            # Priority: credentials > config > env vars
            conn_str = (
                self.credentials.get("connection_string")
                or self.config.get("connection_string")
                or os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
            )
            account_name = (
                self.credentials.get("account_name")
                or self.config.get("storage_account_name")
                or self.config.get("account_name")
                or os.environ.get("AZURE_STORAGE_ACCOUNT_NAME", "")
            )
            account_key = (
                self.credentials.get("account_key")
                or self.config.get("account_key")
                or os.environ.get("AZURE_STORAGE_ACCOUNT_KEY", "")
            )

            if conn_str:
                self._client = BlobServiceClient.from_connection_string(
                    conn_str, connection_verify=self._get_ssl_ca_path()
                )
            elif account_name and account_key:
                account_url = f"https://{account_name}.blob.core.windows.net"
                self._client = BlobServiceClient(
                    account_url=account_url, credential=account_key,
                    connection_verify=self._get_ssl_ca_path()
                )
            else:
                raise RuntimeError(
                    "Azure Blob Storage credentials not configured. "
                    "Provide connection_string OR account_name + account_key "
                    "via connector config, credentials, or environment variables "
                    "(AZURE_STORAGE_CONNECTION_STRING, AZURE_STORAGE_ACCOUNT_NAME, AZURE_STORAGE_ACCOUNT_KEY)."
                )
        return self._client

    @property
    def container_name(self) -> str:
        return (
            self.credentials.get("container_name")
            or self.config.get("container_name")
            or os.environ.get("AZURE_STORAGE_CONTAINER_NAME", "")
        )

    async def test_connection(self) -> dict:
        start = time.monotonic()
        try:
            client = self._get_client()
            containers = []
            async for container in client.list_containers():
                containers.append(container.name)
                if len(containers) >= 1:
                    break
            latency = int((time.monotonic() - start) * 1000)
            return {"success": True, "latency_ms": latency, "message": f"Connected. Found containers."}
        except Exception as e:
            latency = int((time.monotonic() - start) * 1000)
            return {"success": False, "latency_ms": latency, "message": str(e)}

    async def discover_schema(self) -> dict:
        client = self._get_client()
        schema = {"containers": []}
        async for container in client.list_containers():
            container_client = client.get_container_client(container.name)
            blobs = []
            async for blob in container_client.list_blobs():
                blobs.append({
                    "name": blob.name,
                    "size": blob.size,
                    "content_type": blob.content_settings.content_type if blob.content_settings else None,
                    "last_modified": str(blob.last_modified) if blob.last_modified else None,
                })
                if len(blobs) >= 100:
                    break
            schema["containers"].append({
                "name": container.name,
                "blobs": blobs,
            })
        return schema

    async def execute_query(self, query: str, params: Optional[dict] = None) -> list[dict]:
        """For blob storage, query is the container/blob path pattern."""
        client = self._get_client()
        container = self.container_name or (query.split("/")[0] if "/" in query else query)
        container_client = client.get_container_client(container)
        prefix = query.split("/", 1)[1] if "/" in query else ""
        results = []
        async for blob in container_client.list_blobs(name_starts_with=prefix):
            results.append({
                "name": blob.name,
                "size": blob.size,
                "content_type": blob.content_settings.content_type if blob.content_settings else None,
            })
        return results

    async def write(self, resource: str, payload: dict) -> dict:
        client = self._get_client()
        container = self.container_name or "default"
        blob_name = payload.get("blob_name", resource)
        data = payload.get("data", b"")
        container_client = client.get_container_client(container)
        blob_client = container_client.get_blob_client(blob_name)
        await blob_client.upload_blob(data, overwrite=True)
        return {"uploaded": blob_name, "container": container}

    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None
