"""
Finance System MCP Server (SAP-like)
Provides tools for expense reports, invoices, and budget information.
"""

from fastmcp import FastMCP
from datetime import datetime
import sys
import os

# Load environment variables from .env file
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(env_path)

# Add auth module to path for Okta validation
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from auth.okta_validator import validate_authorization_header

mcp = FastMCP("Finance System")

# Mock expense reports
EXPENSE_REPORTS = {
    "EXP001": {
        "id": "EXP001",
        "employee_id": "EMP001",
        "title": "Q1 Conference Travel",
        "amount": 2500,
        "status": "Approved",
        "submitted_date": "2026-01-15",
        "approved_date": "2026-01-20",
        "items": [
            {"description": "Flight", "amount": 1200},
            {"description": "Hotel", "amount": 900},
            {"description": "Meals", "amount": 400}
        ]
    },
    "EXP002": {
        "id": "EXP002",
        "employee_id": "EMP002",
        "title": "Office Supplies",
        "amount": 350,
        "status": "Pending",
        "submitted_date": "2026-01-23",
        "approved_date": None,
        "items": [
            {"description": "Laptop Stand", "amount": 150},
            {"description": "USB Cables", "amount": 50},
            {"description": "Monitor", "amount": 150}
        ]
    }
}

# Mock invoices
INVOICES = {
    "INV001": {
        "id": "INV001",
        "vendor": "Acme Software Inc",
        "amount": 15000,
        "status": "Paid",
        "invoice_date": "2026-01-10",
        "due_date": "2026-02-10",
        "paid_date": "2026-01-22"
    },
    "INV002": {
        "id": "INV002",
        "vendor": "Cloud Services Ltd",
        "amount": 5000,
        "status": "Pending",
        "invoice_date": "2026-01-15",
        "due_date": "2026-02-15",
        "paid_date": None
    }
}

# Mock budget data
BUDGETS = {
    "Engineering": {
        "department": "Engineering",
        "annual_budget": 1000000,
        "spent": 420000,
        "remaining": 580000,
        "headcount": 25
    },
    "Finance": {
        "department": "Finance",
        "annual_budget": 500000,
        "spent": 180000,
        "remaining": 320000,
        "headcount": 10
    },
    "HR": {
        "department": "HR",
        "annual_budget": 300000,
        "spent": 95000,
        "remaining": 205000,
        "headcount": 5
    }
}


@mcp.tool
def get_expense_report(expense_id: str) -> dict:
    """Get an expense report by ID"""
    if expense_id in EXPENSE_REPORTS:
        return {"success": True, "expense_report": EXPENSE_REPORTS[expense_id]}
    return {"success": False, "error": f"Expense report {expense_id} not found"}


@mcp.tool
def list_expense_reports(employee_id: str = None) -> dict:
    """List expense reports (optionally filtered by employee)"""
    reports = list(EXPENSE_REPORTS.values())
    if employee_id:
        reports = [r for r in reports if r["employee_id"] == employee_id]
    
    return {
        "success": True,
        "count": len(reports),
        "expense_reports": reports
    }


@mcp.tool
def submit_expense_report(employee_id: str, title: str, amount: float, items: list) -> dict:
    """Submit a new expense report"""
    report_id = f"EXP{len(EXPENSE_REPORTS) + 1:03d}"
    
    report = {
        "id": report_id,
        "employee_id": employee_id,
        "title": title,
        "amount": amount,
        "status": "Pending",
        "submitted_date": datetime.now().isoformat(),
        "approved_date": None,
        "items": items
    }
    
    EXPENSE_REPORTS[report_id] = report
    return {
        "success": True,
        "message": f"Expense report {report_id} submitted",
        "report": report
    }


@mcp.tool
def get_invoice(invoice_id: str) -> dict:
    """Get an invoice by ID"""
    if invoice_id in INVOICES:
        return {"success": True, "invoice": INVOICES[invoice_id]}
    return {"success": False, "error": f"Invoice {invoice_id} not found"}


@mcp.tool
def list_invoices(status: str = None) -> dict:
    """List invoices (optionally filtered by status)"""
    invoices = list(INVOICES.values())
    if status:
        invoices = [i for i in invoices if i["status"].lower() == status.lower()]
    
    return {
        "success": True,
        "count": len(invoices),
        "invoices": invoices
    }


@mcp.tool
def get_department_budget(department: str) -> dict:
    """Get budget information for a department"""
    if department in BUDGETS:
        return {"success": True, "budget": BUDGETS[department]}
    return {"success": False, "error": f"Budget for {department} not found"}


@mcp.tool
def list_all_budgets() -> dict:
    """List all department budgets"""
    budgets = list(BUDGETS.values())
    total_budget = sum(b["annual_budget"] for b in budgets)
    total_spent = sum(b["spent"] for b in budgets)
    
    return {
        "success": True,
        "count": len(budgets),
        "total_budget": total_budget,
        "total_spent": total_spent,
        "total_remaining": total_budget - total_spent,
        "budgets": budgets
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--http":
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8002
        
        import uvicorn
        from starlette.applications import Starlette
        from starlette.responses import StreamingResponse
        from starlette.routing import Route
        from starlette.requests import Request
        import json
        
        print(f"Starting Finance System MCP server on http://localhost:{port}/mcp")
        
        app = Starlette()
        
        async def mcp_handler(request: Request):
            """HTTP endpoint for MCP protocol with Okta token validation."""
            try:
                # Get authorization header
                auth_header = request.headers.get("Authorization")
                session_id = request.headers.get("Mcp-Session-Id")
                
                body = await request.body()
                request_text = body.decode()
                
                print(f"\n[Finance MCP DEBUG] ===== INCOMING REQUEST =====")
                print(f"[Finance MCP DEBUG] Session ID: {session_id}")
                print(f"[Finance MCP DEBUG] Authorization header: {'Present' if auth_header else 'Missing'}")
                print(f"[Finance MCP DEBUG] Request body: {request_text[:150]}")
                
                async def generate_responses():
                    try:
                        if not request_text.strip():
                            return
                        
                        for line in request_text.strip().split('\n'):
                            if not line.strip():
                                continue
                            
                            message = json.loads(line)
                            
                            if message.get("method") == "initialize":
                                print(f"[Finance MCP DEBUG] Initialize request - no token validation needed")
                                response = {
                                    "jsonrpc": "2.0",
                                    "id": message.get("id"),
                                    "result": {
                                        "protocolVersion": "2025-11-25",
                                        "capabilities": {"tools": {}},
                                        "serverInfo": {
                                            "name": "Finance System MCP",
                                            "version": "1.0.0"
                                        }
                                    }
                                }
                            elif message.get("method") == "tools/list":
                                print(f"[Finance MCP DEBUG] tools/list - validating Okta token...")
                                token_claims = await validate_authorization_header(auth_header)
                                if not token_claims:
                                    print(f"[Finance MCP DEBUG] ❌ TOKEN VALIDATION FAILED")
                                    response = {
                                        "jsonrpc": "2.0",
                                        "id": message.get("id"),
                                        "error": {
                                            "code": -32001,
                                            "message": "Unauthorized - Invalid or missing Okta token"
                                        }
                                    }
                                    yield json.dumps(response).encode() + b'\n'
                                    continue
                                print(f"[Finance MCP DEBUG] ✅ TOKEN VALIDATED - sub: {token_claims.get('sub')}, aud: {token_claims.get('aud')}")
                                
                                response = {
                                    "jsonrpc": "2.0",
                                    "id": message.get("id"),
                                    "result": {
                                        "tools": [
                                            {
                                                "name": "get_expense_report",
                                                "description": "Get an expense report by ID",
                                                "inputSchema": {
                                                    "type": "object",
                                                    "properties": {
                                                        "expense_id": {"type": "string"}
                                                    },
                                                    "required": ["expense_id"]
                                                }
                                            },
                                            {
                                                "name": "list_expense_reports",
                                                "description": "List expense reports (optionally filtered by employee)",
                                                "inputSchema": {
                                                    "type": "object",
                                                    "properties": {
                                                        "employee_id": {"type": "string"}
                                                    }
                                                }
                                            },
                                            {
                                                "name": "get_invoice",
                                                "description": "Get an invoice by ID",
                                                "inputSchema": {
                                                    "type": "object",
                                                    "properties": {
                                                        "invoice_id": {"type": "string"}
                                                    },
                                                    "required": ["invoice_id"]
                                                }
                                            },
                                            {
                                                "name": "list_invoices",
                                                "description": "List invoices (optionally filtered by status)",
                                                "inputSchema": {
                                                    "type": "object",
                                                    "properties": {
                                                        "status": {"type": "string"}
                                                    }
                                                }
                                            },
                                            {
                                                "name": "get_department_budget",
                                                "description": "Get a department's budget",
                                                "inputSchema": {
                                                    "type": "object",
                                                    "properties": {
                                                        "department": {"type": "string"}
                                                    },
                                                    "required": ["department"]
                                                }
                                            },
                                            {
                                                "name": "list_all_budgets",
                                                "description": "List all department budgets",
                                                "inputSchema": {
                                                    "type": "object",
                                                    "properties": {}
                                                }
                                            }
                                        ]
                                    }
                                }
                            elif message.get("method") == "tools/call":
                                print(f"[Finance MCP DEBUG] tools/call - validating Okta token...")
                                token_claims = await validate_authorization_header(auth_header)
                                if not token_claims:
                                    print(f"[Finance MCP DEBUG] ❌ TOKEN VALIDATION FAILED")
                                    response = {
                                        "jsonrpc": "2.0",
                                        "id": message.get("id"),
                                        "error": {
                                            "code": -32001,
                                            "message": "Unauthorized - Invalid or missing Okta token"
                                        }
                                    }
                                    yield json.dumps(response).encode() + b'\n'
                                    continue
                                print(f"[Finance MCP DEBUG] ✅ TOKEN VALIDATED - sub: {token_claims.get('sub')}, aud: {token_claims.get('aud')}")
                                
                                tool_name = message.get("params", {}).get("name")
                                tool_args = message.get("params", {}).get("arguments", {})
                                
                                try:
                                    if tool_name == "get_expense_report":
                                        result = get_expense_report(tool_args.get("expense_id"))
                                    elif tool_name == "list_expense_reports":
                                        result = list_expense_reports(tool_args.get("employee_id"))
                                    elif tool_name == "get_invoice":
                                        result = get_invoice(tool_args.get("invoice_id"))
                                    elif tool_name == "list_invoices":
                                        result = list_invoices(tool_args.get("status"))
                                    elif tool_name == "get_department_budget":
                                        result = get_department_budget(tool_args.get("department"))
                                    elif tool_name == "list_all_budgets":
                                        result = list_all_budgets()
                                    else:
                                        result = {"success": False, "error": f"Unknown tool: {tool_name}"}
                                    
                                    response = {
                                        "jsonrpc": "2.0",
                                        "id": message.get("id"),
                                        "result": {
                                            "content": [
                                                {
                                                    "type": "text",
                                                    "text": json.dumps(result)
                                                }
                                            ]
                                        }
                                    }
                                except Exception as e:
                                    response = {
                                        "jsonrpc": "2.0",
                                        "id": message.get("id"),
                                        "error": {
                                            "code": -32603,
                                            "message": f"Error calling tool: {str(e)}"
                                        }
                                    }
                            elif message.get("method") == "notifications/initialized":
                                continue
                            else:
                                response = {
                                    "jsonrpc": "2.0",
                                    "id": message.get("id"),
                                    "error": {
                                        "code": -32601,
                                        "message": f"Method not found: {message.get('method')}"
                                    }
                                }
                            
                            yield json.dumps(response).encode() + b'\n'
                    
                    except Exception as e:
                        import traceback
                        yield json.dumps({
                            "jsonrpc": "2.0",
                            "error": {
                                "code": -32603,
                                "message": str(e)
                            }
                        }).encode() + b'\n'
                
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
        
        app.routes.append(Route("/mcp", mcp_handler, methods=["POST"]))
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    else:
        mcp.run()
