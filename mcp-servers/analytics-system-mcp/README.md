# Analytics System MCP Server

An unofficial prototype MCP server providing business analytics functionality with **static API key authentication**. For evaluation and testing purposes only.

## Overview

The Analytics System MCP Server provides:
- ✅ Sales analytics and reporting
- ✅ Revenue metrics and dashboards
- ✅ Customer analytics
- ✅ Performance data access
- ✅ **Static API key authentication** for tool access
- ✅ HTTP/NDJSON streaming support (FastMCP)

## Authentication

This server uses **static pre-shared API key** authentication:
- **Auth Method**: API Key header
- **Header**: `X-API-Key: analytics-system-demo-key`
- **Token Validation**: Simple key matching (no JWT)

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run in HTTP mode (for Okta MCP Adapter)
python main.py --http 8003
```

## Configuration

### API Key Authentication

The server validates the `X-API-Key` header for all tool calls:
```bash
X-API-Key: analytics-system-demo-key
```

### Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `get_sales_metrics` | Get sales metrics for period | `period: str (daily/weekly/monthly)` |
| `get_revenue_forecast` | Get revenue forecast | `months: int` |
| `get_customer_analytics` | Get customer metrics | `segment: str (optional)` |
| `get_dashboard_data` | Get dashboard summary | None |

## Usage Examples

### Direct via VS Code/Copilot
```bash
# Endpoint
http://localhost:8003/mcp

# Authentication
X-API-Key: analytics-system-demo-key
```

### Via Okta MCP Adapter Gateway
```bash
# Gateway will:
# 1. Receive request from client
# 2. Route to Analytics System MCP
# 3. Add X-API-Key header (from config)
```

## Implementation Details

- **Framework**: FastMCP 3.0.0b1
- **Server**: Uvicorn (async HTTP)
- **Protocol**: MCP (Model Context Protocol) with NDJSON streaming
- **Auth Method**: Static pre-shared key
- **Domain**: Business analytics/BI system mockup

## Request Flow

```
Client Request
    ↓
Initialize (no auth needed)
    ↓
tools/list (no auth needed for listing)
    ↓
tools/call (API key validated)
    ↓
Response
```

## Troubleshooting

**Authentication fails**: Verify `X-API-Key` header is correct

**Port already in use**: Change port in startup command: `python main.py --http 8004`

**Module not found**: Run `pip install -r requirements.txt`

## Project Structure

```
analytics-system-mcp/
├── main.py              # FastMCP server with HTTP handler
└── requirements.txt     # Python dependencies
```

## Testing

```bash
# Using curl with API key
curl -X POST http://localhost:8003/mcp \
  -H "X-API-Key: analytics-system-demo-key" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
  }'
```

## References

- [MCP Specification](https://modelcontextprotocol.io/)
- [FastMCP Documentation](https://gofastmcp.com/)

## Status

⚠️ **Unofficial Prototype** - For evaluation and testing only. Not for production use.

License: Apache 2.0
