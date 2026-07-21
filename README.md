# Monday Briefing Agent — O4AA Hackathon

An AI agent that assembles a team lead's Monday-morning briefing — org/time-off,
budget status, open tickets, system health — by pulling from four internal
backend systems. Every one of those four connections is secured through Okta
for AI Agents (O4AA), covering both resource-connection types from the O4AA
Patterns deck in a single demo:

| System | Style | O4AA mechanism |
|---|---|---|
| HR (Workday-like) | native OAuth | XAA — client_credentials against a custom Okta authorization server |
| Finance (SAP-like) | native OAuth | XAA — client_credentials against a custom Okta authorization server |
| Ticketing (Jira-like) | static API key | Key vaulted in Okta Privileged Access, fetched just-in-time |
| Analytics (DataDog-like) | static API key | Key vaulted in Okta Privileged Access, fetched just-in-time |

Category: **Meeting Preparation**. The agent itself is registered as an AI
Agent object in Okta Universal Directory with a human owner, so the whole
lifecycle — discovery, onboarding, least-privilege scopes, and (stretch) a
kill switch — is demoable, not just the four API calls.

## Layout

```
mcp-servers/           four sample backend MCP servers (vendored from
                        oktaforai-okta/sample-mcp-servers), unmodified except
                        for tenant-specific .env values
briefing-agent/         the agent: calls all four MCPs, narrates the result
```

## Running locally

1. Start each backend MCP server in its own terminal:
   ```bash
   cd mcp-servers/hr-system-mcp        && cp env.example .env && python main.py --http 8001
   cd mcp-servers/finance-system-mcp   && cp env.example .env && python main.py --http 8002
   cd mcp-servers/analytics-system-mcp && python main.py --http 8003
   cd mcp-servers/ticketing-system-mcp && python main.py --http 8004
   ```
   HR and Finance need their `.env` filled in with the tenant domain and the
   custom authorization server ID created below.

2. Configure and run the agent:
   ```bash
   cd briefing-agent
   pip install -r requirements.txt
   cp .env.example .env   # fill in Okta + Anthropic values
   python main.py
   ```

## Okta tenant setup (ligalac.okta.com)

Fully provisioned: AI Agent object in UD (owned, with a front-door app),
two custom authorization servers (least-privilege scoped), and an
OPA-vaulted secret — see `SETUP.md` for the exact steps and every gotcha
hit while building this, so it's reproducible on a different tenant.
Not yet done: a live kill-switch / access-certification demo.

## Demoing this to a customer

See `DEMO_GUIDE.md` for a talk track, anticipated questions, and — just as
important — an honest list of what this demo does *not* yet prove (the
backend data is internal-ops, not customer/account data; there's no kill
switch demo). Don't oversell past that list.
