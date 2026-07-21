"""
HR System MCP Server (Workday-like)
Provides tools for employee information, time off requests, and payroll.
"""

from fastmcp import FastMCP
import json
from datetime import datetime, timedelta
import sys
import os

# Load environment variables from .env file
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(env_path)

# When True (default), tools/list without auth returns 401. When False, allows unauthenticated tools/list (e.g. for gateway registration).
_protected_discovery_raw = os.getenv("PROTECTED_DISCOVERY", "true").strip().lower()
PROTECTED_DISCOVERY = _protected_discovery_raw in ("true", "1", "yes")

# Add auth module to path for Okta validation
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from auth.okta_validator import validate_authorization_header

mcp = FastMCP("HR System")

# Tool list returned by tools/list (shared for protected and unprotected discovery)
HR_TOOLS_LIST = [
    {"name": "get_employee", "description": "Get employee information by employee ID", "inputSchema": {"type": "object", "properties": {"employee_id": {"type": "string"}}, "required": ["employee_id"]}},
    {"name": "list_employees", "description": "List all employees in the system", "inputSchema": {"type": "object", "properties": {}}},
]

# Mock employee database
EMPLOYEES = {
    "EMP001": {
        "id": "EMP001",
        "name": "Alice Johnson",
        "email": "alice@company.com",
        "department": "Engineering",
        "position": "Senior Engineer",
        "salary": 150000,
        "hire_date": "2020-01-15"
    },
    "EMP002": {
        "id": "EMP002",
        "name": "Bob Smith",
        "email": "bob@company.com",
        "department": "Finance",
        "position": "Financial Analyst",
        "salary": 85000,
        "hire_date": "2021-06-01"
    },
    "EMP003": {
        "id": "EMP003",
        "name": "Carol Davis",
        "email": "carol@company.com",
        "department": "HR",
        "position": "HR Manager",
        "salary": 95000,
        "hire_date": "2019-03-10"
    }
}

# Mock payroll data
PAYROLL = {
    "EMP001": {
        "employee_id": "EMP001",
        "gross_salary": 150000,
        "net_salary": 112500,
        "taxes": 37500,
        "last_payment": "2026-01-24",
        "next_payment": "2026-02-07"
    },
    "EMP002": {
        "employee_id": "EMP002",
        "gross_salary": 85000,
        "net_salary": 63750,
        "taxes": 21250,
        "last_payment": "2026-01-24",
        "next_payment": "2026-02-07"
    }
}

# Mock time off requests
TIME_OFF_REQUESTS = [
    {
        "id": "TOF001",
        "employee_id": "EMP001",
        "type": "Vacation",
        "start_date": "2026-02-10",
        "end_date": "2026-02-17",
        "status": "Approved",
        "days": 5
    },
    {
        "id": "TOF002",
        "employee_id": "EMP002",
        "type": "Sick Leave",
        "start_date": "2026-02-02",
        "end_date": "2026-02-02",
        "status": "Pending",
        "days": 1
    }
]


@mcp.tool
def get_employee(employee_id: str) -> dict:
    """Get employee information by employee ID"""
    if employee_id in EMPLOYEES:
        return {"success": True, "employee": EMPLOYEES[employee_id]}
    return {"success": False, "error": f"Employee {employee_id} not found"}


@mcp.tool
def list_employees() -> dict:
    """List all employees in the system"""
    employees = list(EMPLOYEES.values())
    return {
        "success": True,
        "count": len(employees),
        "employees": employees
    }


@mcp.tool
def get_employee_payroll(employee_id: str) -> dict:
    """Get payroll information for an employee"""
    if employee_id in PAYROLL:
        return {"success": True, "payroll": PAYROLL[employee_id]}
    return {"success": False, "error": f"Payroll data not found for {employee_id}"}


@mcp.tool
def request_time_off(employee_id: str, time_off_type: str, start_date: str, end_date: str) -> dict:
    """Request time off for an employee"""
    if employee_id not in EMPLOYEES:
        return {"success": False, "error": f"Employee {employee_id} not found"}
    
    request_id = f"TOF{len(TIME_OFF_REQUESTS) + 1:03d}"
    
    # Calculate days
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    days = (end - start).days + 1
    
    request = {
        "id": request_id,
        "employee_id": employee_id,
        "type": time_off_type,
        "start_date": start_date,
        "end_date": end_date,
        "status": "Pending",
        "days": days,
        "requested_on": datetime.now().isoformat()
    }
    
    TIME_OFF_REQUESTS.append(request)
    return {
        "success": True,
        "message": f"Time off request {request_id} created",
        "request": request
    }


@mcp.tool
def get_time_off_requests(employee_id: str = None) -> dict:
    """Get time off requests (optionally filtered by employee ID)"""
    if employee_id:
        requests = [r for r in TIME_OFF_REQUESTS if r["employee_id"] == employee_id]
    else:
        requests = TIME_OFF_REQUESTS
    
    return {
        "success": True,
        "count": len(requests),
        "requests": requests
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--http":
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8001
        
        import uvicorn
        from starlette.applications import Starlette
        from starlette.responses import StreamingResponse
        from starlette.routing import Route
        from starlette.requests import Request
        import json
        import asyncio
        from contextlib import asynccontextmanager
        
        print(f"Starting HR System MCP server on http://localhost:{port}/mcp (PROTECTED_DISCOVERY={PROTECTED_DISCOVERY})")
        
        # Create Starlette app
        app = Starlette()
        
        # We'll use the FastMCP server instance to handle messages
        # FastMCP needs proper async handling for the protocol
        
        async def handle_mcp_message(message, auth_header):
            """Process a single MCP JSON-RPC message and return the response dict (or None for notifications)."""
            if message.get("method") == "initialize":
                print(f"[HR MCP DEBUG] Initialize request - no token validation needed")
                return {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "result": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "HR System MCP", "version": "1.0.0"}
                    }
                }

            elif message.get("method") == "tools/list":
                if not PROTECTED_DISCOVERY and not auth_header:
                    print(f"[HR MCP DEBUG] tools/list without auth (PROTECTED_DISCOVERY=false): returning tool list")
                    return {
                        "jsonrpc": "2.0",
                        "id": message.get("id"),
                        "result": {"tools": HR_TOOLS_LIST}
                    }
                print(f"[HR MCP DEBUG] tools/list - validating Okta token...")
                token_claims = await validate_authorization_header(auth_header)
                if not token_claims:
                    print(f"[HR MCP DEBUG] ❌ TOKEN VALIDATION FAILED")
                    return {
                        "jsonrpc": "2.0",
                        "id": message.get("id"),
                        "error": {"code": -32001, "message": "Unauthorized - Invalid or missing Okta token"}
                    }
                print(f"[HR MCP DEBUG] ✅ TOKEN VALIDATED - sub: {token_claims.get('sub')}, aud: {token_claims.get('aud')}")
                return {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "result": {"tools": HR_TOOLS_LIST}
                }

            elif message.get("method") == "tools/call":
                print(f"[HR MCP DEBUG] tools/call - validating Okta token...")
                token_claims = await validate_authorization_header(auth_header)
                if not token_claims:
                    print(f"[HR MCP DEBUG] ❌ TOKEN VALIDATION FAILED")
                    return {
                        "jsonrpc": "2.0",
                        "id": message.get("id"),
                        "error": {"code": -32001, "message": "Unauthorized - Invalid or missing Okta token"}
                    }
                print(f"[HR MCP DEBUG] ✅ TOKEN VALIDATED - sub: {token_claims.get('sub')}, aud: {token_claims.get('aud')}")

                tool_name = message.get("params", {}).get("name")
                tool_args = message.get("params", {}).get("arguments", {})
                try:
                    if tool_name == "get_employee":
                        result = get_employee(tool_args.get("employee_id"))
                    elif tool_name == "list_employees":
                        result = list_employees()
                    elif tool_name == "get_employee_payroll":
                        result = get_employee_payroll(tool_args.get("employee_id"))
                    elif tool_name == "request_time_off":
                        result = request_time_off(tool_args.get("employee_id"), tool_args.get("time_off_type"), tool_args.get("start_date"), tool_args.get("end_date"))
                    elif tool_name == "get_time_off_requests":
                        result = get_time_off_requests(tool_args.get("employee_id"))
                    else:
                        result = {"success": False, "error": f"Unknown tool: {tool_name}"}
                    return {
                        "jsonrpc": "2.0",
                        "id": message.get("id"),
                        "result": {"content": [{"type": "text", "text": json.dumps(result)}]}
                    }
                except Exception as e:
                    return {
                        "jsonrpc": "2.0",
                        "id": message.get("id"),
                        "error": {"code": -32603, "message": f"Error calling tool: {str(e)}"}
                    }

            elif message.get("method") == "notifications/initialized":
                return None

            else:
                return {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "error": {"code": -32601, "message": f"Method not found: {message.get('method')}"}
                }

        async def mcp_post_handler(request: Request):
            """
            POST /mcp — handle MCP JSON-RPC requests.
            Responds with application/json for single messages (Gateway compatible)
            or application/x-ndjson for batches.
            """
            try:
                auth_header = request.headers.get("Authorization")
                session_id = request.headers.get("Mcp-Session-Id")

                body = await request.body()
                request_text = body.decode()

                print(f"\n[HR MCP DEBUG] ===== INCOMING REQUEST =====")
                print(f"[HR MCP DEBUG] Session ID: {session_id}")
                print(f"[HR MCP DEBUG] Authorization header: {'Present' if auth_header else 'Missing'}")
                print(f"[HR MCP DEBUG] Request body: {request_text[:150]}")

                if not request_text.strip():
                    from starlette.responses import JSONResponse
                    return JSONResponse({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Empty request"}}, status_code=400)

                lines = [l for l in request_text.strip().split('\n') if l.strip()]

                if len(lines) == 1:
                    message = json.loads(lines[0])
                    response_obj = await handle_mcp_message(message, auth_header)
                    if response_obj is None:
                        from starlette.responses import Response
                        return Response(status_code=204)
                    from starlette.responses import JSONResponse
                    return JSONResponse(response_obj)

                async def generate_ndjson():
                    for line in lines:
                        message = json.loads(line)
                        response_obj = await handle_mcp_message(message, auth_header)
                        if response_obj is not None:
                            yield json.dumps(response_obj).encode() + b'\n'

                return StreamingResponse(
                    generate_ndjson(),
                    media_type="application/x-ndjson",
                    headers={"Cache-Control": "no-cache"}
                )

            except Exception as e:
                from starlette.responses import JSONResponse
                return JSONResponse(
                    {"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}},
                    status_code=500
                )

        async def mcp_get_handler(request: Request):
            """
            GET /mcp — SSE endpoint for server-initiated notifications.
            The AgentCore Gateway opens this after initialize to listen for events.
            """
            print(f"[HR MCP DEBUG] GET /mcp — SSE stream opened")

            async def event_stream():
                # Keep connection alive; no server-initiated events in this simple server
                while True:
                    yield f": keepalive\n\n".encode()
                    await asyncio.sleep(30)

            return StreamingResponse(
                event_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
            )

        # Add MCP endpoints — POST for messages, GET for SSE stream
        app.routes.append(Route("/mcp", mcp_post_handler, methods=["POST"]))
        app.routes.append(Route("/mcp", mcp_get_handler, methods=["GET"]))
        
        # Run HTTP server
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    else:
        # Default stdio mode
        mcp.run()
