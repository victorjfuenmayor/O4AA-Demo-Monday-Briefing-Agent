# Finance System MCP Server

An unofficial prototype MCP server providing SAP-like finance system functionality with **Okta token validation**. For evaluation and testing purposes only.

## Overview

The Finance System MCP Server provides:
- ✅ Expense report management
- ✅ Invoice tracking
- ✅ Budget information
- ✅ Financial data access
- ✅ **Okta OAuth 2.0 token validation** for all tool calls
- ✅ HTTP/NDJSON streaming support (FastMCP)

## Authentication

This server validates Okta access tokens for all tool calls (except `initialize`):
- **Token Source**: Okta authorization server
- **Validation**: JWT signature, expiration, audience claims
- **Authorization Header**: `Authorization: Bearer <access_token>`

## Quick Start

```bash
# Setup
cp env.example .env
# Edit .env with your Okta credentials

# Install dependencies
pip install -r requirements.txt

# Run in HTTP mode (for Okta MCP Adapter)
python main.py --http 8002
```

## Configuration

### .env (Environment Variables)
```bash
OKTA_DOMAIN=ijtestcustom.oktapreview.com
OKTA_AUTHORIZATION_SERVER_ID=auss2fth0mcIXHzVO1d7
OKTA_AUDIENCE=
OKTA_REQUIRED_SCOPES=
```

### Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `get_expense_report` | Get expense report by ID | `expense_id: str` |
| `list_expense_reports` | List expense reports | `employee_id: str (optional)` |
| `submit_expense_report` | Submit new expense report | `employee_id: str, title: str, amount: float, items: list` |
| `get_invoice` | Get invoice by ID | `invoice_id: str` |
| `list_invoices` | List invoices | `status: str (optional)` |
| `get_budget` | Get department budget | `department: str` |
| `list_budgets` | List all budgets | None |

## Usage Examples

### Direct via VS Code/Copilot
```bash
# Endpoint
http://localhost:8002/mcp

# Authorization
Authorization: Bearer <okta_access_token>
```

### Via Okta MCP Adapter Gateway
```bash
# Gateway will:
# 1. Receive request from client
# 2. Validate Okta token
# 3. Forward to Finance System MCP
# 4. Attach authorization header
```

## Implementation Details

- **Framework**: FastMCP 3.0.0b1
- **Server**: Uvicorn (async HTTP)
- **Protocol**: MCP (Model Context Protocol) with NDJSON streaming
- **Token Validation**: JWKS-based JWT validation with signature verification
- **Domain**: SAP-like finance system mockup
- **Caching**: JWKS keys cached with TTL

## Request Flow

```
Client Request
    ↓
Authorization Header (Okta token)
    ↓
Initialize (no token needed)
    ↓
tools/list (validate token)
    ↓
tools/call (validate token)
    ↓
Response
```

## Troubleshooting

**Token validation fails**: Verify `OKTA_DOMAIN` and `OKTA_AUTHORIZATION_SERVER_ID` in `.env`

**Port already in use**: Change port in startup command: `python main.py --http 8003`

**Missing environment variables**: Copy `env.example` to `.env` and fill in values

**JWKS fetch error**: Verify Okta domain and authorization server ID are correct

## Project Structure

```
finance-system-mcp/
├── main.py              # FastMCP server with HTTP handler
├── requirements.txt     # Python dependencies
├── env.example         # Environment template
└── auth/
    ├── __init__.py
    └── okta_validator.py  # Okta token validation
```

## Testing

```bash
# Using curl with Okta token
curl -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer <your_okta_token>" \
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
- [Okta Developer Docs](https://developer.okta.com/)

## Status

⚠️ **Unofficial Prototype** - For evaluation and testing only. Not for production use.

License: Apache 2.0
