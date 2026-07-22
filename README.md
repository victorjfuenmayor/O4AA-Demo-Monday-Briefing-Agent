# Monday Briefing Agent — O4AA Hackathon

An AI agent that assembles a team lead's Monday-morning briefing — org/time-off,
budget status, open tickets, system health, team shoutouts — by pulling from
internal backend systems. Every connection is secured through Okta for AI
Agents (O4AA), covering **five** genuinely different resource-connection
patterns in a single demo (four working live today, one built and wired but
currently paused on an Okta-side config step):

| System | Style | O4AA mechanism |
|---|---|---|
| HR (Workday-like) | native OAuth | **AI Agent token exchange (OAuth STS)** via a **Resource Server** — real end-user chain of custody, one-time consent |
| Finance (SAP-like) | native OAuth | `client_credentials` against a custom Okta authorization server |
| Ticketing (Jira-like) | native OAuth | **AI Agent token exchange (OAuth STS)** via an **MCP Server** — same chain-of-custody mechanism as HR, but the authorization server is auto-discovered instead of hand-entered |
| Analytics (DataDog-like) | static API key | Key vaulted in Okta Privileged Access, fetched just-in-time |
| Kudos Wall (Bonusly-like) | native OAuth | **Real Cross-App Access (ID-JAG)** — admin-defined access, no per-user consent; the resource runs its **own** authorization server. Built and wired end-to-end; currently paused on an Okta API Scopes declaration (see `SETUP.md` §12) |

HR and Ticketing are the standout pair: both use Okta's **native AI Agent
token exchange**, authenticated with a `private_key_jwt` assertion signed by
the AI Agent's own key pair (not any app's client_secret) — but registered
two different ways. HR is a **Resource Server** (you tell Okta the
authorize/token endpoints yourself); Ticketing is an **MCP Server** (Okta
auto-discovers them by calling the resource's own `/.well-known/oauth-protected-resource`
endpoint, which requires the resource to be live-reachable from Okta's cloud
at registration time — we used an `ngrok` tunnel for the local demo server).
The resulting access token in both cases carries **both** the agent's
identity (`cid`) and the real logged-in user's identity (`sub`/`uid`) —
genuine chain of custody, not just an app-only credential. HR falls back to
plain `client_credentials` when run via the CLI with no logged-in user;
Ticketing has no such fallback (its authorization server only allows
`authorization_code`) and is simply skipped in that case. See the in-app
"MCP Server vs Resource Server" button on the briefing agent's front door,
or `SETUP.md` §10, for the full comparison.

We also fully implemented **real Cross-App Access** (the IETF
ID-JAG/token-exchange draft — a different, separate protocol from the STS
mechanism above): Okta's own "Agent0"/"Todo0" XAA sample apps were already
installed on this tenant (renamed here to "XAA Requester"/"Kudos Wall"),
just never enabled — see `SETUP.md` §8 for the original (partially
incorrect) investigation and §12 for the corrected, working recipe. Unlike
every other pattern here, the resource runs its **own** authorization
server (`mcp-servers/kudos-wall-mcp/`) rather than relying on one of
Okta's. It's fully wired end-to-end and currently paused one step short of
working, on an Okta API Scopes declaration.

Category: **Meeting Preparation**. The agent itself is registered as an AI
Agent object in Okta Universal Directory with a human owner, so the whole
lifecycle — discovery, onboarding, least-privilege scopes, and (stretch) a
kill switch — is demoable, not just the API calls.

The Streamlit UI includes a language selector (top of the sidebar) that
switches the entire experience — including the long per-resource
explanations and the generated briefing itself — between English (US),
Spanish (Latin America), and Brazilian Portuguese. See `SETUP.md` §13.

## Layout

```
mcp-servers/           sample backend MCP servers (vendored from
                        oktaforai-okta/sample-mcp-servers, unmodified except
                        for tenant-specific .env values) plus kudos-wall-mcp/
                        (built for this demo -- also runs its own
                        authorization server, see SETUP.md §12)
briefing-agent/         main.py (agent + CLI), app.py (Streamlit UI),
                        auth.py (Okta login -- two separate flows, see
                        SETUP.md §12), okta_auth.py (O4AA credential
                        brokering), resources.py (connection registry),
                        call_log.py (live Okta<->MCP trace, redacted,
                        shown in the Streamlit sidebar), i18n.py
                        (EN/ES/PT-BR translations for the whole UI, see
                        SETUP.md §13)
```

## Running locally

1. Start each backend MCP server in its own terminal:
   ```bash
   cd mcp-servers/hr-system-mcp        && cp env.example .env && python main.py --http 8001
   cd mcp-servers/finance-system-mcp   && cp env.example .env && python main.py --http 8002
   cd mcp-servers/analytics-system-mcp && python main.py --http 8003
   cd mcp-servers/ticketing-system-mcp && python main.py --http 8004
   cd mcp-servers/kudos-wall-mcp       && python main.py --http 8005   # paused, see SETUP.md §12
   ```
   HR and Finance need their `.env` filled in with the tenant domain and the
   custom authorization server ID created below. Ticketing and Kudos Wall
   each need a public `ngrok` tunnel (see SETUP.md §10 and §12) since Okta
   discovers/validates against them live.

2. Configure and run the agent:
   ```bash
   cd briefing-agent
   pip install -r requirements.txt
   cp .env.example .env   # fill in Okta + Anthropic values
   python main.py                 # CLI
   streamlit run app.py           # or: browser UI, gated behind Okta login
   ```

## Okta tenant setup

Fully provisioned: AI Agent object in UD (owned, with a linked front-door
app and its own signing key pair), a Resource Server + STS connection for
HR, an MCP Server + STS connection for Ticketing (behind an `ngrok` tunnel
during registration), custom authorization servers (least-privilege
scoped) for HR/Finance/Ticketing, an OPA-vaulted secret for Analytics, and
Okta's own XAA sample app pair (renamed "XAA Requester"/"Kudos Wall") with
Cross-App Access enabled and pointed at a self-hosted authorization server
— see `SETUP.md` for the exact steps and every gotcha hit while building
this, so it's reproducible on a different tenant.
Not yet done: finishing Kudos Wall's Okta API Scopes declaration (§12), a
live kill-switch / access-certification demo.

## Demoing this to a customer

See `DEMO_GUIDE.md` for a talk track, anticipated questions, and — just as
important — an honest list of what this demo does *not* yet prove (the
backend data is internal-ops, not customer/account data; there's no kill
switch demo). Don't oversell past that list.
