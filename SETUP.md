# Setup Runbook — provisioning this demo on a new Okta tenant

This walks through everything needed to reproduce the Monday Briefing Agent
demo on a different tenant, including every gotcha hit while building it on
`ligalac.okta.com`. Steps 1–4 use the core Identity Management API
(`https://{org}.okta.com/api/v1/...`, `Authorization: SSWS {token}`). Step 5
uses the *separate* Okta Privileged Access API
(`https://{org}.pam.okta.com/v1/teams/{team}/...`) — different product,
different subdomain, different credentials. Step 6 is console-only today.

## Prerequisites

- Okta org API token (Security → API → Tokens) with admin rights.
- Okta Privileged Access (OPA) provisioned for the org, and console access to
  it (`https://{org}.pam.okta.com/t/{team_name}/home`).
- Anthropic API key (a direct one — see gotcha below).
- Python 3.11+.

## 1. Vendor the sample MCP servers

```bash
git clone https://github.com/oktaforai-okta/sample-mcp-servers /tmp/smp
cp -r /tmp/smp/{hr,finance,ticketing,analytics}-system-mcp mcp-servers/
```

**Gotcha:** as shipped, `finance-system-mcp` and `analytics-system-mcp` only
wire 2 of their ~6 tools into the HTTP `tools/list`/`tools/call` dispatch,
even though every tool's Python function is fully implemented in the same
file (the FastMCP `@mcp.tool` decorators work, but the manual HTTP JSON-RPC
shim these samples ship with for Bridge/Gateway compatibility never routes
to the rest). This repo's copies are already patched — see the `elif
tool_name == "..."` chains in both `main.py` files if you pull a fresh copy
and need to redo it.

## 2. Create the agent's own OAuth client (backend identity)

```bash
POST /api/v1/apps
{
  "name": "oidc_client",
  "label": "<agent name>",
  "signOnMode": "OPENID_CONNECT",
  "credentials": {"oauthClient": {"token_endpoint_auth_method": "client_secret_basic"}},
  "settings": {"oauthClient": {
    "redirect_uris": [],
    "response_types": ["token"],
    "grant_types": ["client_credentials"],
    "application_type": "service",
    "consent_method": "TRUSTED"
  }}
}
```

Save the returned `client_id` / `credentials.oauthClient.client_secret` —
this is `OKTA_AGENT_CLIENT_ID` / `OKTA_AGENT_CLIENT_SECRET`.

## 3. Create one custom authorization server per XAA-native resource

Repeat per resource (HR, Finance, ...):

```bash
POST /api/v1/authorizationServers
{ "name": "<label>", "audiences": ["api://<resource-id>"] }

POST /api/v1/authorizationServers/{id}/scopes
{ "name": "<resource>.read", "displayName": "...", "consent": "IMPLICIT" }

POST /api/v1/authorizationServers/{id}/policies
{
  "type": "OAUTH_AUTHORIZATION_POLICY", "status": "ACTIVE",
  "name": "Agent Policy",
  "conditions": {"clients": {"include": ["<agent client_id from step 2>"]}}
}

POST /api/v1/authorizationServers/{id}/policies/{policy_id}/rules
{
  "type": "RESOURCE_ACCESS", "status": "ACTIVE", "name": "Allow client_credentials",
  "conditions": {"grantTypes": {"include": ["client_credentials"]}, "scopes": {"include": ["<resource>.read"]}},
  "actions": {"token": {"accessTokenLifetimeMinutes": 60}}
}
```

Sanity-check before moving on:

```bash
curl -X POST "https://{org}/oauth2/{auth_server_id}/v1/token" \
  -u "<client_id>:<client_secret>" \
  -d "grant_type=client_credentials&scope=<resource>.read"
# should return an access_token
```

Fill each resource MCP server's own `.env` (copy `env.example`):
`OKTA_DOMAIN`, `OKTA_AUTHORIZATION_SERVER_ID`, `OKTA_AUDIENCE=api://<resource-id>`,
`OKTA_REQUIRED_SCOPES=<resource>.read`.

## 4. Okta Privileged Access (OPA) — vaulting static-key resources

**Gotcha:** OPA is a fully separate API/product from core Identity. The org
API token from step 1 does *not* work here.

1. In the OPA console → **Directory → Users → Service Users** tab → create
   one → **Create API Key**. Copy the `key_id` (a UUID) and `key_secret`
   *immediately* — OPA shows the secret exactly once.
2. Exchange for a bearer token (expires in ~1hr, re-exchange as needed):
   ```bash
   POST https://{org}.pam.okta.com/v1/teams/{team}/service_token
   { "key_id": "...", "key_secret": "..." }
   ```
3. Create the actual secret **by hand in the OPA console** (Secrets
   section), not via API — the create/update API requires client-side JWE
   encryption against OPA's public key, which is real work for zero benefit
   on a demo secret you're creating once. Store a JSON object as the value
   so one secret can hold multiple named keys, e.g.
   `{"ticketing-system-demo-key": "...", "analytics-system-demo-key": "..."}`.
4. **Grant the Service User read/reveal access** to that secret (or its
   folder/project) — a freshly created Service User has *no* grants by
   default and will get `401`/`404`-ish "not authorized" errors otherwise.
5. Get the three IDs needed to address the secret by opening it in the
   console and reading them out of the URL:
   `.../secrets/resource_groups/{resource_group_id}/projects/{project_id}/secret/{secret_id}`.
6. Fill `OPA_DOMAIN`, `OPA_TEAM_NAME`, `OPA_KEY_ID`, `OPA_KEY_SECRET`,
   `OPA_RESOURCE_GROUP_ID`, `OPA_PROJECT_ID`, `OPA_SECRET_ID` into
   `briefing-agent/.env`.

**Gotcha (reveal mechanics):** OPA never just sends you the secret. You
generate an ephemeral RSA keypair, POST the public key to
`/resource_groups/{rg}/projects/{proj}/secrets/{secret_id}`, OPA re-encrypts
the secret as a JWE using your public key, and you decrypt locally. See
`_opa_reveal_secret()` in `briefing-agent/okta_auth.py` — it's the whole
mechanism in ~15 lines with `jwcrypto`.

## 5. Register the agent in Universal Directory

Console-only today (no confirmed public Management API endpoint for this
EA feature as of writing) — navigate to
`/admin/workload-principals/ai-agents/register`.

**Gotcha:** the form's "Application" field only lists apps with a real,
*visible*, interactive login flow. A pure `client_credentials` service app
(like the one from step 2) is hidden by default
(`visibility.hide.web/iOS = true`) and won't appear — and you can't just
flip that flag, because Okta requires `idp_initiated_login.mode` to be
non-`DISABLED` (which itself requires an `initiate_login_uri`) before it'll
let a visible app have no login flow.

Fix: create a small dedicated **front-door app** purely to satisfy this
field — it's never actually used for login:

```bash
POST /api/v1/apps
{
  "name": "oidc_client", "label": "<agent name> - Front Door",
  "signOnMode": "OPENID_CONNECT",
  "settings": {"oauthClient": {
    "redirect_uris": ["http://localhost:3000/callback"],
    "response_types": ["code"], "grant_types": ["authorization_code"],
    "application_type": "web", "consent_method": "TRUSTED",
    "initiate_login_uri": "http://localhost:3000/login",
    "idp_initiated_login": {"mode": "SPEC", "default_scope": []}
  }}
}
```
Then PUT `visibility.hide.web` / `.iOS` to `false` on it. It'll now show up
in the picker. (If your agent has a real end-user-facing app already, just
use that instead of creating a placeholder.)

Once registered, add **Resource Connections**:
- For each custom authorization server: **Only Allow**, scoped to the
  *specific* scope that server issues (not "Allow all", even when there's
  only one scope — this is the least-privilege story, make it explicit).
- For OPA-vaulted resources: add a **Secret** connection and pick it by
  name; it resolves to an ORN like `orn:okta:pam:{org_id}:secrets:{secret_id}`.

## 6. Run it

```bash
# one terminal per server
cd mcp-servers/hr-system-mcp        && python main.py --http 8001
cd mcp-servers/finance-system-mcp   && python main.py --http 8002
cd mcp-servers/analytics-system-mcp && python main.py --http 8003
cd mcp-servers/ticketing-system-mcp && python main.py --http 8004

cd briefing-agent && python main.py
```

Expect a "Receipts" panel confirming all four connections, followed by the
narrated briefing. If a connection fails, the receipts panel tells you
which one and the traceback tells you why — it's a short pipeline.

**Gotcha (unrelated to Okta):** if narration throws `AuthenticationError`
mentioning `LiteLLM_VerificationTokenTable`, the Anthropic key you were
given is scoped to an internal proxy, not `api.anthropic.com` directly — get
a direct key or the proxy's base URL (`ANTHROPIC_BASE_URL`).
