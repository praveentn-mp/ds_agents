"""Filesystem connector — delegates to Docker MCP filesystem server."""

import time
import os
from typing import Optional
from backend.connectors.base import BaseConnector


class FilesystemConnector(BaseConnector):
    def __init__(self, name: str, config: dict, credentials: Optional[dict] = None):
        super().__init__(name, config, credentials)
        self.base_path = config.get("base_path", "/tmp/adf-files")

    async def test_connection(self) -> dict:
        start = time.monotonic()
        try:
            exists = os.path.isdir(self.base_path)
            latency = int((time.monotonic() - start) * 1000)
            if exists:
                return {"success": True, "latency_ms": latency, "message": f"Path {self.base_path} accessible"}
            else:
                return {"success": False, "latency_ms": latency, "message": f"Path {self.base_path} not found"}
        except Exception as e:
            latency = int((time.monotonic() - start) * 1000)
            return {"success": False, "latency_ms": latency, "message": str(e)}

    async def discover_schema(self) -> dict:
        schema = {"directories": []}
        for root, dirs, files in os.walk(self.base_path):
            rel_root = os.path.relpath(root, self.base_path)
            schema["directories"].append({
                "path": rel_root,
                "files": [
                    {
                        "name": f,
                        "size": os.path.getsize(os.path.join(root, f)),
                        "extension": os.path.splitext(f)[1],
                    }
                    for f in files
                ],
                "subdirs": dirs,
            })
        return schema

    async def execute_query(self, query: str, params: Optional[dict] = None) -> list[dict]:
        """List files matching the query pattern."""
        import glob
        pattern = os.path.join(self.base_path, query)
        results = []
        for path in glob.glob(pattern, recursive=True):
            stat = os.stat(path)
            results.append({
                "path": os.path.relpath(path, self.base_path),
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "is_dir": os.path.isdir(path),
            })
        return results

    async def write(self, resource: str, payload: dict) -> dict:
        file_path = os.path.join(self.base_path, resource)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        content = payload.get("content", "")
        with open(file_path, "w") as f:
            f.write(content)
        return {"written": resource, "size": len(content)}

    async def close(self):
        pass
