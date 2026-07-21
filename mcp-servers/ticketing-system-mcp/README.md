# Ticketing System MCP Server

An unofficial prototype MCP server providing IT ticketing/service desk functionality with **static API key authentication**. For evaluation and testing purposes only.

## Overview

The Ticketing System MCP Server provides:
- ✅ Issue/ticket creation and management
- ✅ Ticket status tracking
- ✅ Incident reporting
- ✅ Service request handling
- ✅ **Static API key authentication** for tool access
- ✅ HTTP/NDJSON streaming support (FastMCP)

## Authentication

This server uses **static pre-shared API key** authentication:
- **Auth Method**: API Key header
- **Header**: `X-API-Key: ticketing-system-demo-key`
- **Token Validation**: Simple key matching (no JWT)

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run in HTTP mode (for Okta MCP Adapter)
python main.py --http 8004
```

## Configuration

### API Key Authentication

The server validates the `X-API-Key` header for all tool calls:
```bash
X-API-Key: ticketing-system-demo-key
```

### Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `create_ticket` | Create new support ticket | `title: str, description: str, priority: str, assigned_to: str (optional)` |
| `get_ticket` | Get ticket by ID | `ticket_id: str` |
| `list_tickets` | List tickets | `status: str (optional), assigned_to: str (optional)` |
| `update_ticket_status` | Update ticket status | `ticket_id: str, status: str` |
| `add_ticket_comment` | Add comment to ticket | `ticket_id: str, comment: str` |

## Usage Examples

### Direct via VS Code/Copilot
```bash
# Endpoint
http://localhost:8004/mcp

# Authentication
X-API-Key: ticketing-system-demo-key
```

### Via Okta MCP Adapter Gateway
```bash
# Gateway will:
# 1. Receive request from client
# 2. Route to Ticketing System MCP
# 3. Add X-API-Key header (from config)
```

## Implementation Details

- **Framework**: FastMCP 3.0.0b1
- **Server**: Uvicorn (async HTTP)
- **Protocol**: MCP (Model Context Protocol) with NDJSON streaming
- **Auth Method**: Static pre-shared key
- **Domain**: IT ticketing/service desk mockup

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

**Port already in use**: Change port in startup command: `python main.py --http 8005`

**Module not found**: Run `pip install -r requirements.txt`

## Project Structure

```
ticketing-system-mcp/
├── main.py              # FastMCP server with HTTP handler
└── requirements.txt     # Python dependencies
```

## Testing

```bash
# Using curl with API key
curl -X POST http://localhost:8004/mcp \
  -H "X-API-Key: ticketing-system-demo-key" \
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
