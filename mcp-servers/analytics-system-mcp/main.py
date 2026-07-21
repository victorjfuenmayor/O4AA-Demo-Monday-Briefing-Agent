"""
Analytics/Monitoring MCP Server (DataDog-like)
Provides tools for querying logs, dashboards, and metrics.
"""

from fastmcp import FastMCP
from datetime import datetime, timedelta

mcp = FastMCP("Analytics System")

# Mock logs
LOGS = [
    {
        "timestamp": (datetime.now() - timedelta(minutes=5)).isoformat(),
        "service": "api-gateway",
        "level": "INFO",
        "message": "Request processed successfully",
        "request_id": "req-12345"
    },
    {
        "timestamp": (datetime.now() - timedelta(minutes=10)).isoformat(),
        "service": "database",
        "level": "WARNING",
        "message": "High query latency detected",
        "query_time_ms": 2500
    },
    {
        "timestamp": (datetime.now() - timedelta(minutes=15)).isoformat(),
        "service": "auth-service",
        "level": "ERROR",
        "message": "Authentication failed for user",
        "user_id": "USER123"
    },
    {
        "timestamp": (datetime.now() - timedelta(minutes=20)).isoformat(),
        "service": "api-gateway",
        "level": "INFO",
        "message": "Service health check passed",
        "status": "healthy"
    }
]

# Mock dashboards
DASHBOARDS = {
    "dash-001": {
        "id": "dash-001",
        "name": "System Health",
        "description": "Overall system health and metrics",
        "panels": 8,
        "last_updated": datetime.now().isoformat()
    },
    "dash-002": {
        "id": "dash-002",
        "name": "API Performance",
        "description": "API response times and throughput",
        "panels": 6,
        "last_updated": (datetime.now() - timedelta(hours=1)).isoformat()
    },
    "dash-003": {
        "id": "dash-003",
        "name": "Database Metrics",
        "description": "Database performance and query analysis",
        "panels": 10,
        "last_updated": datetime.now().isoformat()
    }
}

# Mock metrics
METRICS = {
    "api.response_time": {
        "name": "api.response_time",
        "unit": "ms",
        "current_value": 145,
        "average": 138,
        "min": 50,
        "max": 2500
    },
    "database.query_time": {
        "name": "database.query_time",
        "unit": "ms",
        "current_value": 280,
        "average": 250,
        "min": 100,
        "max": 5000
    },
    "server.cpu_usage": {
        "name": "server.cpu_usage",
        "unit": "%",
        "current_value": 45,
        "average": 42,
        "min": 15,
        "max": 85
    },
    "server.memory_usage": {
        "name": "server.memory_usage",
        "unit": "%",
        "current_value": 62,
        "average": 58,
        "min": 40,
        "max": 92
    }
}


@mcp.tool
def query_logs(service: str = None, level: str = None, limit: int = 10) -> dict:
    """Query logs (optionally filtered by service and log level)"""
    logs = LOGS.copy()
    
    if service:
        logs = [log for log in logs if log["service"].lower() == service.lower()]
    
    if level:
        logs = [log for log in logs if log["level"].upper() == level.upper()]
    
    logs = logs[:limit]
    
    return {
        "success": True,
        "count": len(logs),
        "logs": logs
    }


@mcp.tool
def list_dashboards() -> dict:
    """List all available dashboards"""
    dashboards = list(DASHBOARDS.values())
    return {
        "success": True,
        "count": len(dashboards),
        "dashboards": dashboards
    }


@mcp.tool
def get_dashboard(dashboard_id: str) -> dict:
    """Get dashboard details by ID"""
    if dashboard_id in DASHBOARDS:
        return {"success": True, "dashboard": DASHBOARDS[dashboard_id]}
    return {"success": False, "error": f"Dashboard {dashboard_id} not found"}


@mcp.tool
def get_metric(metric_name: str) -> dict:
    """Get a specific metric by name"""
    if metric_name in METRICS:
        return {"success": True, "metric": METRICS[metric_name]}
    return {"success": False, "error": f"Metric {metric_name} not found"}


@mcp.tool
def list_metrics() -> dict:
    """List all available metrics"""
    metrics = list(METRICS.values())
    return {
        "success": True,
        "count": len(metrics),
        "metrics": metrics
    }


@mcp.tool
def get_alert_history(limit: int = 20) -> dict:
    """Get recent alerts"""
    alerts = [
        {
            "id": "alert-001",
            "name": "High CPU Usage",
            "severity": "Warning",
            "timestamp": (datetime.now() - timedelta(minutes=30)).isoformat(),
            "resolved": True
        },
        {
            "id": "alert-002",
            "name": "Database Latency",
            "severity": "Critical",
            "timestamp": (datetime.now() - timedelta(minutes=15)).isoformat(),
            "resolved": False
        },
        {
            "id": "alert-003",
            "name": "Low Disk Space",
            "severity": "Warning",
            "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(),
            "resolved": True
        }
    ]
    
    return {
        "success": True,
        "count": len(alerts),
        "alerts": alerts[:limit]
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--http":
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8003
        
        import uvicorn
        from starlette.applications import Starlette
        from starlette.responses import StreamingResponse
        from starlette.routing import Route
        from starlette.requests import Request
        import json
        
        print(f"Starting Analytics System MCP server on http://localhost:{port}/mcp")
        
        app = Starlette()
        
        async def mcp_handler(request: Request):
            """HTTP endpoint for MCP protocol using StreamableHttpTransport."""
            try:
                body = await request.body()
                request_text = body.decode()
                
                async def generate_responses():
                    try:
                        if not request_text.strip():
                            return
                        
                        for line in request_text.strip().split('\n'):
                            if not line.strip():
                                continue
                            
                            message = json.loads(line)
                            
                            if message.get("method") == "initialize":
                                response = {
                                    "jsonrpc": "2.0",
                                    "id": message.get("id"),
                                    "result": {
                                        "protocolVersion": "2025-11-25",
                                        "capabilities": {"tools": {}},
                                        "serverInfo": {
                                            "name": "Analytics System MCP",
                                            "version": "1.0.0"
                                        }
                                    }
                                }
                            elif message.get("method") == "tools/list":
                                response = {
                                    "jsonrpc": "2.0",
                                    "id": message.get("id"),
                                    "result": {
                                        "tools": [
                                            {
                                                "name": "query_logs",
                                                "description": "Query logs (optionally filtered by service and log level)",
                                                "inputSchema": {
                                                    "type": "object",
                                                    "properties": {
                                                        "service": {"type": "string"},
                                                        "level": {"type": "string"}
                                                    }
                                                }
                                            },
                                            {
                                                "name": "list_metrics",
                                                "description": "List all available metrics",
                                                "inputSchema": {
                                                    "type": "object",
                                                    "properties": {}
                                                }
                                            },
                                            {
                                                "name": "list_dashboards",
                                                "description": "List all dashboards",
                                                "inputSchema": {
                                                    "type": "object",
                                                    "properties": {}
                                                }
                                            },
                                            {
                                                "name": "get_dashboard",
                                                "description": "Get a dashboard by ID",
                                                "inputSchema": {
                                                    "type": "object",
                                                    "properties": {
                                                        "dashboard_id": {"type": "string"}
                                                    },
                                                    "required": ["dashboard_id"]
                                                }
                                            },
                                            {
                                                "name": "get_metric",
                                                "description": "Get a metric by name",
                                                "inputSchema": {
                                                    "type": "object",
                                                    "properties": {
                                                        "metric_name": {"type": "string"}
                                                    },
                                                    "required": ["metric_name"]
                                                }
                                            },
                                            {
                                                "name": "get_alert_history",
                                                "description": "Get recent alert history",
                                                "inputSchema": {
                                                    "type": "object",
                                                    "properties": {
                                                        "limit": {"type": "integer"}
                                                    }
                                                }
                                            }
                                        ]
                                    }
                                }
                            elif message.get("method") == "tools/call":
                                tool_name = message.get("params", {}).get("name")
                                tool_args = message.get("params", {}).get("arguments", {})

                                try:
                                    if tool_name == "query_logs":
                                        result = query_logs(tool_args.get("service"), tool_args.get("level"))
                                    elif tool_name == "list_metrics":
                                        result = list_metrics()
                                    elif tool_name == "list_dashboards":
                                        result = list_dashboards()
                                    elif tool_name == "get_dashboard":
                                        result = get_dashboard(tool_args.get("dashboard_id"))
                                    elif tool_name == "get_metric":
                                        result = get_metric(tool_args.get("metric_name"))
                                    elif tool_name == "get_alert_history":
                                        result = get_alert_history(tool_args.get("limit", 20))
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
