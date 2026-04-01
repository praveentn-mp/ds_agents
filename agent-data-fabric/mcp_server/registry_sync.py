"""Registry sync — polls backend DB to sync resources into MCP server."""

import asyncio
import logging

logger = logging.getLogger("adf.mcp.registry_sync")


class RegistrySync:
    """Background task that syncs connector/server registrations from DB to MCP."""

    def __init__(self, poll_interval: int = 30):
        self.poll_interval = poll_interval
        self._running = False

    async def start(self):
        self._running = True
        logger.info("Registry sync started")
        while self._running:
            try:
                await self._sync()
            except Exception as e:
                logger.error(f"Registry sync error: {e}")
            await asyncio.sleep(self.poll_interval)

    async def _sync(self):
        """Poll the backend API for current state and sync."""
        import httpx
        import os
        try:
            backend_url = os.environ.get("BACKEND_URL", "http://localhost:7790")
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{backend_url}/capabilities", timeout=10.0)
                if response.status_code == 200:
                    data = response.json()
                    logger.debug(f"Synced: {len(data.get('connectors', []))} connectors, {len(data.get('mcp_tools', []))} tools")
        except Exception as e:
            logger.debug(f"Sync poll failed (backend may not be ready): {e}")

    def stop(self):
        self._running = False
