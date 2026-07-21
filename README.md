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

## Okta tenant setup (ligalac.okta.com) — done

- [x] **AI Agent object in Universal Directory** ("Monday Briefing Agent"),
      linked to a front-door OIDC app (`Monday Briefing Agent - Front Door`,
      created purely to satisfy the registration flow's login-flow
      requirement — the agent has no real end-user login).
- [x] **OAuth service app** (`Hackathon - Monday Briefing Agent`,
      `client_credentials`) for the agent's own backend identity —
      `OKTA_AGENT_CLIENT_ID`/`SECRET`.
- [x] **Two custom authorization servers** — `Hackathon HR Resource`
      (`hr.read`) and `Hackathon Finance Resource` (`finance.read`) — each
      with an access policy scoped to only the agent's service app.
      Declared on the AI Agent object as resource connections with
      **Only Allow** scoped to exactly that one scope each (least privilege).
      IDs go into `HR_AUTH_SERVER_ID`/`FINANCE_AUTH_SERVER_ID` (agent side)
      and `OKTA_AUTHORIZATION_SERVER_ID` (each MCP server's own `.env`).
- [x] **Okta Privileged Access (OPA) vaulted secret** (`HackathonAccountHelper1`,
      holding both `ticketing-system-demo-key` and `analytics-system-demo-key`)
      fetched just-in-time via OPA's Reveal a Secret JWE flow — see
      `briefing-agent/okta_auth.py`. Declared on the AI Agent object as a
      **Secret** resource connection
      (`orn:okta:pam:...:secrets:f8b035d0-6f08-48e3-ab5e-f43f38d55ec9`).
      Falls back to plain env vars for local dev if `OPA_DOMAIN` isn't set.
- [ ] Stretch, not yet done: wire up a **kill switch** (revoke the agent's
      OAuth grants) and an **access certification** campaign on the agent's
      scopes, to demo governance beyond just the initial connection live.

## Note on the mock data

The vendored servers model *internal* systems (employee/payroll, expense
reports & budgets, dev tickets, system health) rather than customer/account
data — so the narrative is an internal ops briefing for a team lead, not
customer-account research, even though it lands in the same "Meeting
Preparation" category.
