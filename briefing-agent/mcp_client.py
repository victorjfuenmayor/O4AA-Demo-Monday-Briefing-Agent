"""Minimal MCP JSON-RPC client for calling tools over HTTP on the sample
hr/finance/ticketing/analytics servers (see ../mcp-servers). Each server
answers tools/call with {"result": {"content": [{"type": "text", "text": "<json>"}]}}."""

import itertools
import json

from call_log import logged_post

_ids = itertools.count(1)


class MCPClient:
    def __init__(self, base_url: str, auth_header: tuple[str, str] | None = None):
        self.base_url = base_url.rstrip("/") + "/mcp"
        self.auth_header = auth_header

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.auth_header:
            headers[self.auth_header[0]] = self.auth_header[1]
        return headers

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        payload = {
            "jsonrpc": "2.0",
            "id": next(_ids),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        }
        resp = logged_post(
            f"MCP server ({self.base_url}) — tools/call {name}",
            self.base_url,
            json=payload,
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        body = resp.json()
        if "error" in body:
            raise RuntimeError(f"{name} failed: {body['error']}")
        text = body["result"]["content"][0]["text"]
        return json.loads(text)
