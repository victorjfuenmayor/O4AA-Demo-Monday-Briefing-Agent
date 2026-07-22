"""
Ticketing System MCP Server (Jira-like)
Provides tools for creating tickets, adding comments, and transitioning status.
"""

import os
from fastmcp import FastMCP
from datetime import datetime

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

mcp = FastMCP("Ticketing System")

# Mock tickets
TICKETS = {
    "TICKET-001": {
        "id": "TICKET-001",
        "title": "Fix login button styling",
        "description": "Login button has incorrect padding on mobile",
        "status": "In Progress",
        "priority": "Medium",
        "assignee": "Alice Johnson",
        "created_date": "2026-01-20",
        "updated_date": "2026-01-23",
        "project": "Frontend",
        "comments_count": 3
    },
    "TICKET-002": {
        "id": "TICKET-002",
        "title": "Implement user export feature",
        "description": "Add ability to export user data to CSV",
        "status": "Backlog",
        "priority": "High",
        "assignee": "Bob Smith",
        "created_date": "2026-01-15",
        "updated_date": "2026-01-22",
        "project": "Backend",
        "comments_count": 5
    },
    "TICKET-003": {
        "id": "TICKET-003",
        "title": "Database connection pooling issue",
        "description": "Connections not being returned to pool properly",
        "status": "Done",
        "priority": "Critical",
        "assignee": "Carol Davis",
        "created_date": "2026-01-10",
        "updated_date": "2026-01-18",
        "project": "Infrastructure",
        "comments_count": 8
    }
}

# Mock comments
COMMENTS = {
    "TICKET-001": [
        {
            "id": "comment-001",
            "author": "Alice Johnson",
            "text": "I'll start working on this today",
            "created_date": "2026-01-23T10:30:00"
        },
        {
            "id": "comment-002",
            "author": "Bob Smith",
            "text": "Have you checked the mobile viewport sizes?",
            "created_date": "2026-01-23T14:15:00"
        }
    ],
    "TICKET-002": [
        {
            "id": "comment-003",
            "author": "Bob Smith",
            "text": "This feature is critical for the next release",
            "created_date": "2026-01-22T09:00:00"
        }
    ]
}

# Available transitions
VALID_TRANSITIONS = {
    "Backlog": ["In Progress"],
    "In Progress": ["Review", "Backlog"],
    "Review": ["In Progress", "Done"],
    "Done": ["Backlog"]
}


@mcp.tool
def get_ticket(ticket_id: str) -> dict:
    """Get a ticket by ID"""
    if ticket_id in TICKETS:
        ticket = TICKETS[ticket_id].copy()
        ticket["comments"] = COMMENTS.get(ticket_id, [])
        return {"success": True, "ticket": ticket}
    return {"success": False, "error": f"Ticket {ticket_id} not found"}


@mcp.tool
def list_tickets(status: str = None, project: str = None, assignee: str = None) -> dict:
    """List tickets (optionally filtered by status, project, or assignee)"""
    tickets = list(TICKETS.values())
    
    if status:
        tickets = [t for t in tickets if t["status"].lower() == status.lower()]
    if project:
        tickets = [t for t in tickets if t["project"].lower() == project.lower()]
    if assignee:
        tickets = [t for t in tickets if t["assignee"].lower() == assignee.lower()]
    
    return {
        "success": True,
        "count": len(tickets),
        "tickets": tickets
    }


@mcp.tool
def create_ticket(title: str, description: str, project: str, priority: str = "Medium", assignee: str = None) -> dict:
    """Create a new ticket"""
    ticket_id = f"TICKET-{len(TICKETS) + 1:03d}"
    
    ticket = {
        "id": ticket_id,
        "title": title,
        "description": description,
        "status": "Backlog",
        "priority": priority,
        "assignee": assignee or "Unassigned",
        "created_date": datetime.now().isoformat(),
        "updated_date": datetime.now().isoformat(),
        "project": project,
        "comments_count": 0
    }
    
    TICKETS[ticket_id] = ticket
    COMMENTS[ticket_id] = []
    
    return {
        "success": True,
        "message": f"Ticket {ticket_id} created",
        "ticket": ticket
    }


@mcp.tool
def add_comment(ticket_id: str, author: str, text: str) -> dict:
    """Add a comment to a ticket"""
    if ticket_id not in TICKETS:
        return {"success": False, "error": f"Ticket {ticket_id} not found"}
    
    comment = {
        "id": f"comment-{len(COMMENTS.get(ticket_id, [])) + 1:03d}",
        "author": author,
        "text": text,
        "created_date": datetime.now().isoformat()
    }
    
    if ticket_id not in COMMENTS:
        COMMENTS[ticket_id] = []
    
    COMMENTS[ticket_id].append(comment)
    TICKETS[ticket_id]["comments_count"] += 1
    TICKETS[ticket_id]["updated_date"] = datetime.now().isoformat()
    
    return {
        "success": True,
        "message": f"Comment added to {ticket_id}",
        "comment": comment
    }


@mcp.tool
def transition_ticket(ticket_id: str, new_status: str) -> dict:
    """Transition a ticket to a new status"""
    if ticket_id not in TICKETS:
        return {"success": False, "error": f"Ticket {ticket_id} not found"}
    
    ticket = TICKETS[ticket_id]
    current_status = ticket["status"]
    
    # Check if transition is valid
    valid_transitions = VALID_TRANSITIONS.get(current_status, [])
    if new_status not in valid_transitions:
        return {
            "success": False,
            "error": f"Cannot transition from {current_status} to {new_status}. Valid transitions: {valid_transitions}"
        }
    
    ticket["status"] = new_status
    ticket["updated_date"] = datetime.now().isoformat()
    
    return {
        "success": True,
        "message": f"Ticket {ticket_id} transitioned to {new_status}",
        "ticket": ticket
    }


@mcp.tool
def get_ticket_comments(ticket_id: str) -> dict:
    """Get all comments for a ticket"""
    if ticket_id not in TICKETS:
        return {"success": False, "error": f"Ticket {ticket_id} not found"}
    
    comments = COMMENTS.get(ticket_id, [])
    return {
        "success": True,
        "count": len(comments),
        "comments": comments
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--http":
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8004

        import uvicorn
        from starlette.applications import Starlette
        from starlette.responses import StreamingResponse
        from starlette.routing import Route
        from starlette.requests import Request
        import json

        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from auth.okta_validator import validate_authorization_header

        print(f"Starting Ticketing System MCP server on http://localhost:{port}/mcp")

        app = Starlette()

        async def mcp_handler(request: Request):
            """HTTP endpoint for MCP protocol using StreamableHttpTransport."""
            try:
                body = await request.body()
                request_text = body.decode()
                
                # Debug: Log all incoming headers
                print(f"\n[MCP DEBUG] ===== INCOMING REQUEST =====")
                print(f"[MCP DEBUG] Method: {request.method}")
                print(f"[MCP DEBUG] URL: {request.url}")
                print(f"[MCP DEBUG] All Headers:")
                for header_name, header_value in request.headers.items():
                    print(f"  {header_name}: {header_value}")
                
                # Explicitly check for session ID
                session_id_header = request.headers.get("Mcp-Session-Id")
                session_id_lower = request.headers.get("mcp-session-id")
                print(f"[MCP DEBUG] Mcp-Session-Id header: {session_id_header}")
                print(f"[MCP DEBUG] mcp-session-id header (lowercase): {session_id_lower}")
                print(f"[MCP DEBUG] Request Body: {request_text[:300]}")

                auth_header = request.headers.get("Authorization")
                
                async def generate_responses():
                    try:
                        if not request_text.strip():
                            return
                        
                        for line in request_text.strip().split('\n'):
                            if not line.strip():
                                continue
                            
                            message = json.loads(line)
                            method = message.get("method")
                            request_id = message.get("id")
                            
                            print(f"\n[MCP DEBUG] Processing MCP method: {method} (id: {request_id})")
                            
                            if message.get("method") == "initialize":
                                response = {
                                    "jsonrpc": "2.0",
                                    "id": request_id,
                                    "result": {
                                        "protocolVersion": "2025-11-25",
                                        "capabilities": {"tools": {}},
                                        "serverInfo": {
                                            "name": "Ticketing System MCP",
                                            "version": "1.0.0"
                                        }
                                    }
                                }
                                print(f"[MCP DEBUG] → Responding to initialize")
                            elif message.get("method") == "tools/list":
                                response = {
                                    "jsonrpc": "2.0",
                                    "id": request_id,
                                    "result": {
                                        "tools": [
                                            {
                                                "name": "get_ticket",
                                                "description": "Get a ticket by ID",
                                                "inputSchema": {
                                                    "type": "object",
                                                    "properties": {
                                                        "ticket_id": {"type": "string"}
                                                    },
                                                    "required": ["ticket_id"]
                                                }
                                            },
                                            {
                                                "name": "list_tickets",
                                                "description": "List tickets (optionally filtered by status, project, or assignee)",
                                                "inputSchema": {
                                                    "type": "object",
                                                    "properties": {
                                                        "status": {"type": "string"},
                                                        "project": {"type": "string"}
                                                    }
                                                }
                                            }
                                        ]
                                    }
                                }
                                print(f"[MCP DEBUG] → Responding to tools/list with 2 tools")
                            elif message.get("method") == "tools/call":
                                token_claims = await validate_authorization_header(auth_header)
                                if not token_claims:
                                    response = {
                                        "jsonrpc": "2.0",
                                        "id": request_id,
                                        "error": {
                                            "code": -32001,
                                            "message": "Unauthorized - Invalid or missing Okta token"
                                        }
                                    }
                                    yield json.dumps(response).encode() + b'\n'
                                    continue

                                tool_name = message.get("params", {}).get("name")
                                tool_args = message.get("params", {}).get("arguments", {})
                                print(f"[MCP DEBUG] → Calling tool: {tool_name} with args: {tool_args}")

                                try:
                                    if tool_name == "get_ticket":
                                        result = get_ticket(tool_args.get("ticket_id"))
                                    elif tool_name == "list_tickets":
                                        result = list_tickets(
                                            status=tool_args.get("status"),
                                            project=tool_args.get("project")
                                        )
                                    else:
                                        result = {"success": False, "error": f"Unknown tool: {tool_name}"}
                                    
                                    response = {
                                        "jsonrpc": "2.0",
                                        "id": request_id,
                                        "result": {
                                            "content": [
                                                {
                                                    "type": "text",
                                                    "text": json.dumps(result)
                                                }
                                            ]
                                        }
                                    }
                                    print(f"[MCP DEBUG] → Tool executed successfully")
                                except Exception as e:
                                    response = {
                                        "jsonrpc": "2.0",
                                        "id": request_id,
                                        "error": {
                                            "code": -32603,
                                            "message": f"Error calling tool: {str(e)}"
                                        }
                                    }
                                    print(f"[MCP DEBUG] → Tool error: {str(e)}")
                            elif message.get("method") == "notifications/initialized":
                                print(f"[MCP DEBUG] → Received notification: initialized")
                                continue
                            else:
                                response = {
                                    "jsonrpc": "2.0",
                                    "id": request_id,
                                    "error": {
                                        "code": -32601,
                                        "message": f"Method not found: {message.get('method')}"
                                    }
                                }
                                print(f"[MCP DEBUG] → Unknown method: {message.get('method')}")
                            
                            yield json.dumps(response).encode() + b'\n'
                    
                    except Exception as e:
                        import traceback
                        print(f"[MCP DEBUG] ERROR in response generation: {str(e)}")
                        print(traceback.format_exc())
                        yield json.dumps({
                            "jsonrpc": "2.0",
                            "error": {
                                "code": -32603,
                                "message": str(e)
                            }
                        }).encode() + b'\n'
                
                print(f"[MCP DEBUG] ===== RETURNING STREAMING RESPONSE =====\n")
                return StreamingResponse(
                    generate_responses(),
                    media_type="application/x-ndjson",
                    headers={
                        "Transfer-Encoding": "chunked",
                        "Cache-Control": "no-cache"
                    }
                )
            
            except Exception as e:
                import traceback
                print(f"[MCP DEBUG] ERROR in mcp_handler: {str(e)}")
                print(traceback.format_exc())
                return StreamingResponse(
                    iter([json.dumps({
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32603,
                            "message": str(e)
                        }
                    }).encode() + b'\n']),
                    status_code=500,
                    media_type="application/x-ndjson"
                )
        
        async def protected_resource_metadata(request: Request):
            """RFC 9728 discovery endpoint -- lets Okta's MCP Server
            registration auto-discover which authorization server protects
            this resource."""
            from starlette.responses import JSONResponse
            okta_domain = os.getenv("OKTA_DOMAIN", "").strip()
            auth_server_id = os.getenv("OKTA_AUTHORIZATION_SERVER_ID", "").strip()
            return JSONResponse({
                "resource": str(request.base_url).rstrip("/"),
                "authorization_servers": [f"https://{okta_domain}/oauth2/{auth_server_id}"],
            })

        app.routes.append(Route("/.well-known/oauth-protected-resource", protected_resource_metadata, methods=["GET"]))
        app.routes.append(Route("/mcp", mcp_handler, methods=["POST"]))
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    else:
        mcp.run()
