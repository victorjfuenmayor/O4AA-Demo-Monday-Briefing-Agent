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

## 7. Streamlit front end with Okta login

`briefing-agent/app.py` (`streamlit run app.py`) is a browser UI over the
same `main.py` pipeline, gated behind a real Okta login (Authorization
Code flow) rather than the CLI's no-user mode.

- Reuses the front-door app from step 5 as the login client
  (`OKTA_LOGIN_CLIENT_ID`/`SECRET`/`OKTA_LOGIN_REDIRECT_URI` in `.env`, e.g.
  `http://localhost:8501`) — add that redirect URI to the app's
  `redirect_uris`.
- **Gotcha:** `st.link_button` always opens `target="_blank"` with no way
  to override it, which breaks a redirect-back-to-the-same-tab OAuth flow.
  Use a plain `<a target="_self">` via `st.markdown(..., unsafe_allow_html=True)`
  instead.
- **Gotcha:** `st.session_state` doesn't reliably survive a full external
  redirect (the browser fully leaves the page for Okta and back) — the
  OAuth `state` value needs to live in a plain module-level variable
  instead (see `auth.py`'s `_pending_state`). Fine for a single-user local
  demo; not a substitute for real server-side session storage.

## 8. Real Cross-App Access (XAA) — investigated, not completed

We attempted to replace HR's plain `client_credentials` connection with
real XAA (the actual `draft-ietf-oauth-identity-assertion-authz-grant`
protocol: token-exchange for an ID-JAG, then jwt-bearer to redeem it) rather
than the client_credentials shortcut both HR and Finance use today. Full
write-up of what we found, in order:

1. **Wrong app type is rejected outright.** A generic OIDC app's client_id
   requesting `requested_token_type=urn:ietf:params:oauth:token-type:id-jag`
   gets `'requested_token_type' is invalid or not supported`. Okta requires
   the special catalog integration key `test-cwo-app` ("Cross-App Access
   (XAA) Sample Requesting App") as the requesting-app client. Instantiate
   one via `POST /api/v1/apps {"name": "test-cwo-app", ...}` if your org
   already has a sample of it installed (ours did, apparently provisioned
   for earlier XAA testing — check `GET /api/v1/apps` for a label like
   "Agent0 - Cross App Access (XAA) Sample Requesting App").
2. **That app type can't use a custom authorization server for its own
   login**, even one literally named "default" — `error=unauthorized_client,
   This client cannot use a custom authorization server`. Its login (and,
   per Okta's own blog, the ID-JAG token-exchange call itself) must go
   through the **org authorization server** (`/oauth2/v1/...`, no auth
   server ID segment) — see `developer.okta.com/blog/2026/02/17/xaa-resource-app`:
   *"Only the org authorization server can be used to exchange ID-JAG
   tokens."* We were calling `/oauth2/default/v1/token` (a custom AS
   despite the name) for the exchange — a real bug, not a config gap.
3. **The subject_token's issuing app matters.** An id_token issued to an
   unrelated login app fails with `'subject_token' is invalid` even once
   the endpoint is correct. The user must log in *through the same
   `test-cwo-app`-type app* that performs the exchange, so the token's
   `aud` matches. (We confirmed this both ways: swapping the login app
   back to a generic OIDC app reproduces the failure immediately.)
4. **The user must be assigned to that app.** Zero assignments by default
   → same `'subject_token' is invalid'` error. `POST
   /api/v1/apps/{id}/users/{userId}` fixes it.
5. **Client auth method (Basic vs. body) didn't matter** — Okta's own
   reference client (`oktadev/okta-cross-app-access-mcp`,
   `packages/id-assert-authz-grant-client`) sends `client_id`/`client_secret`
   in the form body; we tried both, no difference in outcome, but matching
   the reference client is still the safer default.
6. **Real blocker: no resource-app registration for HR — and it fails at
   *minting*, not redemption.** Once 1–4 are fixed, the very first call —
   the org-AS token-exchange requesting the ID-JAG — fails with
   `invalid_target: The resource app is not completely configured or user
   is not assigned to the app`. (We initially misread this as a later
   redemption-step failure; it's not — `_get_id_jag()` itself never
   succeeds against this `audience`.) This means Okta's org authorization
   server validates the `audience` parameter against a registry of known
   resource apps *before it will even issue an ID-JAG* — you can't get a
   valid ID-JAG scoped to an unregistered resource under any circumstance,
   which also rules out having the resource self-validate the ID-JAG
   directly (skipping a separate redemption call): the token doesn't exist
   to validate in the first place. Per Okta's blog, fixing this needs a
   **second** catalog integration — "XAA Resource App" — installed *for
   the resource* (HR), with its own Issuer URL pointing at HR's
   authorization server, plus an explicit **Manage Connections** link from
   the requesting app ("Apps providing consent" → add the resource app).
   **This catalog integration does not exist in `ligalac.okta.com`'s app
   catalog.** We confirmed this two ways: the OIN catalog search API
   returns nothing for "XAA"/"cross app access"/"resource"/"cwo"/"todo0",
   *and* it returns nothing even for `test-cwo-app`'s own exact key
   despite that app being directly installable — meaning these internal
   catalog entries aren't indexed by search at all, so the only way to
   find a hidden key is to already know it (e.g. from Okta support/docs),
   not by searching. Per Okta's developer blog, XAA is EA and "no longer
   self-service" — full resource-app support looks like it requires Okta
   to provision it for a given org (contact `xaa@okta.com`), outside
   console/API self-service.
7. **Confirmed the app-type requirement is real, not incidental**, with a
   controlled test: took a generic OIDC app (already granted the
   `token-exchange` grant type, already hitting the correct org-AS
   endpoint) and used it for both login and the exchange call. Got the
   exact original error back — `'requested_token_type' is invalid or not
   supported'` — proving Okta rejects generic OIDC clients for
   `requested_token_type=id-jag` specifically, independent of grant-type
   config or endpoint choice. Only the special `test-cwo-app` catalog type
   is accepted as a requester.
8. **`atko-cross-app-access-sdk` (npm, MIT, beta)** is a real published
   JS/TS SDK for the requester side (`exchangeIdTokenForIdJag`,
   `verifyIdJagToken`) — confirms the org-AS endpoint choice from point 2,
   and its `verifyIdJagToken` implies resources can self-validate an
   ID-JAG's signature/claims instead of redeeming it for a separate access
   token. Doesn't change the point-6 conclusion, since minting itself is
   blocked. `xaa.dev/docs` documents an equivalent "Own Auth Server"
   pattern for resource-app developers (matching the self-hosted
   `oidc-provider`-based authorization server in
   `oktadev/okta-cross-app-access-mcp`'s `packages/authorization-server`)
   — worth exploring if you need a resource-side implementation
   independent of Okta's native (currently unavailable-here) resource-app
   registration, but note it's documentation we couldn't fully load
   (JS-rendered site), and it doesn't remove the need for Okta to
   recognize *some* registered audience before minting an ID-JAG at all.

**Where the code stands:** `okta_auth.py`'s `get_xaa_token_for_user()` /
`_get_id_jag()` are a complete, correct implementation of steps 1–5 above —
left in the file, unused by `main.py`, as a working reference for whenever
the resource-app catalog integration becomes available. `main.py` uses
`get_client_credentials_token()` for both HR and Finance today.
