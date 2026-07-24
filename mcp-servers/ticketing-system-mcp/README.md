# Ticketing System MCP Server

An unofficial prototype MCP server providing IT ticketing/service desk
functionality with **Okta OAuth 2.0 token validation**. For evaluation and
testing purposes only.

## Overview

The Ticketing System MCP Server provides:
- ✅ Issue/ticket creation and management
- ✅ Ticket status tracking
- ✅ Incident reporting
- ✅ Service request handling
- ✅ **Okta OAuth 2.0 token validation** for all tool calls
- ✅ HTTP/NDJSON streaming support (FastMCP)

## Authentication

This server validates Okta access tokens for all tool calls (except
`initialize`) — same validator as every other server in this repo
(`auth/okta_validator.py`, unmodified, config-driven):
- **Token Source**: Okta authorization server
- **Validation**: JWT signature, expiration, audience claims
- **Authorization Header**: `Authorization: Bearer <access_token>`

Registered on the Okta side as an **MCP Server** (not a Resource Server
like HR) — Okta *auto-discovers* which authorization server protects this
resource by calling the RFC 9728 discovery route below, rather than it
being hand-entered in the console. See `SETUP.md` §10 for the full
console-side registration recipe, including why the discovery endpoint
requires this server to be reachable from Okta's cloud at registration
time (an `ngrok` tunnel for local dev).

## Quick Start

```bash
# Setup
cp env.example .env
# Edit .env with your Okta credentials

# Install dependencies
pip install -r requirements.txt

# Run in HTTP mode
python main.py --http 8004
```

## Configuration

### .env (Environment Variables)
```bash
OKTA_DOMAIN=
OKTA_AUTHORIZATION_SERVER_ID=
OKTA_AUDIENCE=
OKTA_REQUIRED_SCOPES=
```
`OKTA_DOMAIN` and `OKTA_AUTHORIZATION_SERVER_ID` are dual-purpose here:
besides validating incoming tokens, they're also used to build this
server's own `/.well-known/oauth-protected-resource` discovery response
(`https://{OKTA_DOMAIN}/oauth2/{OKTA_AUTHORIZATION_SERVER_ID}`) — the
document Okta fetches at registration time to learn which authorization
server protects this resource. Get either one wrong and discovery either
fails outright or silently points Okta at the wrong authorization server.

### Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `get_ticket` | Get ticket by ID | `ticket_id: str` |
| `list_tickets` | List tickets | `status: str (optional), project: str (optional), assignee: str (optional)` |
| `create_ticket` | Create new ticket | `title: str, description: str, project: str, priority: str = "Medium", assignee: str (optional)` |
| `add_comment` | Add comment to a ticket | `ticket_id: str, author: str, text: str` |
| `transition_ticket` | Change a ticket's status | `ticket_id: str, new_status: str` |
| `get_ticket_comments` | Get all comments on a ticket | `ticket_id: str` |

## Usage Examples

### Direct via VS Code/Copilot
```bash
# Endpoint
http://localhost:8004/mcp

# Authorization
Authorization: Bearer <okta_access_token>
```

### Discovery endpoint (what Okta calls at registration time)
```bash
curl http://localhost:8004/.well-known/oauth-protected-resource
# {"resource": "http://localhost:8004", "authorization_servers": ["https://{OKTA_DOMAIN}/oauth2/{OKTA_AUTHORIZATION_SERVER_ID}"]}
```

## Implementation Details

- **Framework**: FastMCP 3.0.0b1
- **Server**: Uvicorn (async HTTP)
- **Protocol**: MCP (Model Context Protocol) with NDJSON streaming
- **Token Validation**: JWKS-based JWT validation with signature verification
- **Discovery**: RFC 9728 `/.well-known/oauth-protected-resource` route
  (`protected_resource_metadata` in `main.py`) — only runs once, at
  registration; editing the Okta-side entry later won't retrigger it.

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

**Token validation fails**: Verify `OKTA_DOMAIN` and
`OKTA_AUTHORIZATION_SERVER_ID` in `.env`

**Port already in use**: Change port in startup command: `python main.py --http 8005`

**Missing environment variables**: Copy `env.example` to `.env` and fill in values

**"No authorization servers were found" during Okta registration**:
the discovery endpoint isn't reachable — verify the `ngrok` tunnel first
with `curl https://<ngrok-url>/.well-known/oauth-protected-resource`, and
remember discovery only runs at *creation* time (delete and recreate the
MCP Server entry after fixing this, editing won't retrigger it).

**No `client_credentials` fallback**: unlike HR, this resource's
authorization-server policy only allows `authorization_code` — there's no
app-only path, so the calling agent must have a logged-in user.

## Project Structure

```
ticketing-system-mcp/
├── main.py              # FastMCP server with HTTP handler + discovery route
├── requirements.txt     # Python dependencies
├── env.example         # Environment template
└── auth/
    ├── __init__.py
    └── okta_validator.py  # Okta token validation (same code as every other server)
```

## Testing

```bash
# Using curl with Okta token
curl -X POST http://localhost:8004/mcp \
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
