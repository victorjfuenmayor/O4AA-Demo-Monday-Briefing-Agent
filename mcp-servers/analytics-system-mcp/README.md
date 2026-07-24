# Analytics System MCP Server

An unofficial prototype MCP server providing business analytics/observability
functionality, modeling a legacy backend with **no OAuth support at all**.
For evaluation and testing purposes only.

## Overview

The Analytics System MCP Server provides:
- ✅ Log querying
- ✅ Dashboard listing/lookup
- ✅ Metric listing/lookup
- ✅ Alert history
- ✅ HTTP/NDJSON streaming support (FastMCP)

## Authentication

**This server does not check any credential today** — `main.py`'s
`mcp_handler` serves `initialize`/`tools/list`/`tools/call` unconditionally,
with no header check anywhere in the request path. This is a real gap
worth knowing about, not a design choice to imitate: the demo's actual
security story for this resource lives entirely on the **caller's** side
(`briefing-agent/okta_auth.get_vaulted_secret()` fetches
`TICKETING_API_KEY`/`ANALYTICS_API_KEY` just-in-time from an Okta
Privileged Access vault rather than static config, and sends it as
`X-API-Key: analytics-system-demo-key`) — but this server itself doesn't
enforce that key server-side. If you're extending this demo and want the
server to actually reject the wrong key, that check needs to be added to
`mcp_handler`; it isn't there yet.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run in HTTP mode
python main.py --http 8003
```

No `.env`/credentials needed to run this server itself, for the reason
above.

### Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `query_logs` | Query recent logs | `service: str (optional), level: str (optional), limit: int = 10` |
| `list_dashboards` | List all dashboards | None |
| `get_dashboard` | Get a dashboard by ID | `dashboard_id: str` |
| `get_metric` | Get a single metric | `metric_name: str` |
| `list_metrics` | List all metrics | None |
| `get_alert_history` | Get recent alert history | `limit: int = 20` |

## Usage Examples

### Direct via VS Code/Copilot
```bash
# Endpoint
http://localhost:8003/mcp
```

## Implementation Details

- **Framework**: FastMCP 3.0.0b1
- **Server**: Uvicorn (async HTTP)
- **Protocol**: MCP (Model Context Protocol) with NDJSON streaming
- **Auth**: none server-side (see above) — client-side vaulting is the
  actual security mechanism this resource demonstrates
- **Domain**: Business analytics/observability system mockup

## Request Flow

```
Client Request
    ↓
Initialize (no auth)
    ↓
tools/list (no auth)
    ↓
tools/call (no auth)
    ↓
Response
```

## Troubleshooting

**Port already in use**: Change port in startup command: `python main.py --http 8003`

**Module not found**: Run `pip install -r requirements.txt`

## Project Structure

```
analytics-system-mcp/
├── main.py              # FastMCP server with HTTP handler
└── requirements.txt     # Python dependencies
```

## Testing

```bash
curl -X POST http://localhost:8003/mcp \
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
