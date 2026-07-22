"""
Kudos Wall MCP Server (Bonusly-like)
Protected by real Cross-App Access (XAA) -- this server IS the resource's
own authorization server (see /v1/token below), not a client of one of
Okta's custom auth servers like the other sample MCP servers in this repo.
"""

import os
import json
import time
import uuid
from datetime import datetime

from fastmcp import FastMCP

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

mcp = FastMCP("Kudos Wall")

KUDOS = [
    {
        "id": "kudos-001",
        "from": "Alice Johnson",
        "to": "Bob Smith",
        "message": "Crushed the Q3 launch under a brutal deadline",
        "category": "shoutout",
        "date": "2026-07-17",
    },
    {
        "id": "kudos-002",
        "from": "Carol Davis",
        "to": "Alice Johnson",
        "message": "Jumped in over the weekend to help unblock the database migration",
        "category": "above-and-beyond",
        "date": "2026-07-18",
    },
    {
        "id": "kudos-003",
        "from": "Bob Smith",
        "to": "Carol Davis",
        "message": "Best onboarding doc I've read all year",
        "category": "shoutout",
        "date": "2026-07-19",
    },
]


@mcp.tool
def list_kudos(recipient: str = None) -> dict:
    """List recent kudos (optionally filtered by recipient)"""
    kudos = KUDOS
    if recipient:
        kudos = [k for k in kudos if k["to"].lower() == recipient.lower()]
    return {"success": True, "count": len(kudos), "kudos": kudos}


@mcp.tool
def give_kudos(from_person: str, to_person: str, message: str, category: str = "shoutout") -> dict:
    """Give a new kudos"""
    kudo = {
        "id": f"kudos-{len(KUDOS) + 1:03d}",
        "from": from_person,
        "to": to_person,
        "message": message,
        "category": category,
        "date": datetime.now().date().isoformat(),
    }
    KUDOS.append(kudo)
    return {"success": True, "message": f"Kudos given to {to_person}", "kudos": kudo}


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--http":
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8005

        import uvicorn
        from starlette.applications import Starlette
        from starlette.responses import StreamingResponse, JSONResponse
        from starlette.routing import Route
        from starlette.requests import Request

        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from auth.okta_validator import validate_authorization_header
        from xaa_resource_as import handle_token_redemption, discovery_document, jwks_document

        print(f"Starting Kudos Wall MCP server on http://localhost:{port}/mcp")

        app = Starlette()

        async def mcp_handler(request: Request):
            try:
                body = await request.body()
                request_text = body.decode()
                auth_header = request.headers.get("Authorization")

                async def generate_responses():
                    if not request_text.strip():
                        return
                    for line in request_text.strip().split("\n"):
                        if not line.strip():
                            continue
                        message = json.loads(line)
                        method = message.get("method")
                        request_id = message.get("id")

                        if method == "initialize":
                            response = {
                                "jsonrpc": "2.0",
                                "id": request_id,
                                "result": {
                                    "protocolVersion": "2025-11-25",
                                    "capabilities": {"tools": {}},
                                    "serverInfo": {"name": "Kudos Wall MCP", "version": "1.0.0"},
                                },
                            }
                        elif method == "tools/list":
                            response = {
                                "jsonrpc": "2.0",
                                "id": request_id,
                                "result": {
                                    "tools": [
                                        {
                                            "name": "list_kudos",
                                            "description": "List recent kudos (optionally filtered by recipient)",
                                            "inputSchema": {
                                                "type": "object",
                                                "properties": {"recipient": {"type": "string"}},
                                            },
                                        },
                                        {
                                            "name": "give_kudos",
                                            "description": "Give a new kudos",
                                            "inputSchema": {
                                                "type": "object",
                                                "properties": {
                                                    "from_person": {"type": "string"},
                                                    "to_person": {"type": "string"},
                                                    "message": {"type": "string"},
                                                    "category": {"type": "string"},
                                                },
                                                "required": ["from_person", "to_person", "message"],
                                            },
                                        },
                                    ]
                                },
                            }
                        elif method == "tools/call":
                            token_claims = await validate_authorization_header(auth_header)
                            if not token_claims:
                                response = {
                                    "jsonrpc": "2.0",
                                    "id": request_id,
                                    "error": {"code": -32001, "message": "Unauthorized - Invalid or missing token"},
                                }
                                yield json.dumps(response).encode() + b"\n"
                                continue

                            tool_name = message.get("params", {}).get("name")
                            tool_args = message.get("params", {}).get("arguments", {})

                            try:
                                if tool_name == "list_kudos":
                                    result = list_kudos(recipient=tool_args.get("recipient"))
                                elif tool_name == "give_kudos":
                                    result = give_kudos(
                                        from_person=tool_args.get("from_person"),
                                        to_person=tool_args.get("to_person"),
                                        message=tool_args.get("message"),
                                        category=tool_args.get("category", "shoutout"),
                                    )
                                else:
                                    result = {"success": False, "error": f"Unknown tool: {tool_name}"}
                                response = {
                                    "jsonrpc": "2.0",
                                    "id": request_id,
                                    "result": {"content": [{"type": "text", "text": json.dumps(result)}]},
                                }
                            except Exception as e:
                                response = {
                                    "jsonrpc": "2.0",
                                    "id": request_id,
                                    "error": {"code": -32603, "message": f"Error calling tool: {str(e)}"},
                                }
                        elif method == "notifications/initialized":
                            continue
                        else:
                            response = {
                                "jsonrpc": "2.0",
                                "id": request_id,
                                "error": {"code": -32601, "message": f"Method not found: {method}"},
                            }
                        yield json.dumps(response).encode() + b"\n"

                return StreamingResponse(
                    generate_responses(),
                    media_type="application/x-ndjson",
                    headers={"Transfer-Encoding": "chunked", "Cache-Control": "no-cache"},
                )
            except Exception as e:
                import traceback
                print(traceback.format_exc())
                return StreamingResponse(
                    iter([json.dumps({"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}}).encode() + b"\n"]),
                    status_code=500,
                    media_type="application/x-ndjson",
                )

        async def token_endpoint(request: Request):
            form = await request.form()
            try:
                result = await handle_token_redemption(dict(form))
                return JSONResponse(result)
            except ValueError as e:
                return JSONResponse({"error": "invalid_grant", "error_description": str(e)}, status_code=400)

        async def discovery_endpoint(request: Request):
            return JSONResponse(discovery_document())

        async def jwks_endpoint(request: Request):
            return JSONResponse(jwks_document())

        app.routes.append(Route("/mcp", mcp_handler, methods=["POST"]))
        # Registered under /oauth2/kudos-wall/ to match {issuer}/v1/token --
        # the same convention Okta's own custom auth servers use, and what
        # okta_auth.get_xaa_token_for_user() posts to.
        app.routes.append(Route("/oauth2/kudos-wall/v1/token", token_endpoint, methods=["POST"]))
        app.routes.append(Route("/oauth2/kudos-wall/.well-known/oauth-authorization-server", discovery_endpoint, methods=["GET"]))
        app.routes.append(Route("/oauth2/kudos-wall/v1/keys", jwks_endpoint, methods=["GET"]))
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    else:
        mcp.run()
