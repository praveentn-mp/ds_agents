"""Docker MCP Hub — container lifecycle and auto-discovery."""

import logging
from typing import Optional

logger = logging.getLogger("adf.docker_hub")


class DockerMCPHub:
    """Manages Docker MCP server containers."""

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import docker
                self._client = docker.from_env()
            except Exception as e:
                logger.warning(f"Docker client not available: {e}")
                raise RuntimeError("Docker is not available. Ensure Colima/Docker is running.")
        return self._client

    async def start_server(self, server) -> dict:
        """Start a Docker MCP server container."""
        client = self._get_client()

        # Check if container already exists
        if server.container_id:
            try:
                container = client.containers.get(server.container_id)
                if container.status != "running":
                    container.start()
                return {
                    "container_id": container.id,
                    "sse_url": server.sse_url,
                }
            except Exception:
                pass

        # Start new container
        labels = {
            "adf.mcp": "true",
            "adf.mcp.name": server.name,
        }

        container = client.containers.run(
            image=server.image,
            name=f"adf-mcp-{server.name}",
            labels=labels,
            detach=True,
            auto_remove=False,
            environment=server.config.get("env", {}),
            volumes=server.config.get("volumes", {}),
            ports=server.config.get("ports", {}),
        )

        sse_url = server.config.get("sse_url", f"http://localhost:{server.config.get('port', 8080)}/sse")

        return {
            "container_id": container.id,
            "sse_url": sse_url,
        }

    async def stop_server(self, server):
        """Stop a Docker MCP server container."""
        if not server.container_id:
            return

        client = self._get_client()
        try:
            container = client.containers.get(server.container_id)
            container.stop(timeout=10)
        except Exception as e:
            logger.warning(f"Error stopping container {server.container_id}: {e}")

    async def list_running(self) -> list[dict]:
        """List all running ADF MCP containers."""
        try:
            client = self._get_client()
            containers = client.containers.list(filters={"label": "adf.mcp=true"})
            return [
                {
                    "container_id": c.id,
                    "name": c.labels.get("adf.mcp.name", c.name),
                    "status": c.status,
                    "image": str(c.image.tags[0]) if c.image.tags else str(c.image.id),
                }
                for c in containers
            ]
        except Exception:
            return []

    async def get_logs(self, container_id: str, tail: int = 100) -> str:
        """Get container logs."""
        client = self._get_client()
        try:
            container = client.containers.get(container_id)
            return container.logs(tail=tail).decode("utf-8")
        except Exception as e:
            return f"Error fetching logs: {e}"
