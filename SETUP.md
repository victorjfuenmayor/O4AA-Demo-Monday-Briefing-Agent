# Setup Runbook — provisioning this demo on a new Okta tenant

This walks through everything needed to reproduce the Monday Briefing Agent
demo on a different tenant, including every gotcha hit while building it on
`ligalac.okta.com`. Steps 1–4 use the core Identity Management API
(`https://{org}.okta.com/api/v1/...`, `Authorization: SSWS {token}`). Step 5
uses the *separate* Okta Privileged Access API
(`https://{org}.pam.okta.com/v1/teams/{team}/...`) — different product,
different subdomain, different credentials. Step 6 is console-only today.
Step 8 (real Cross-App Access / ID-JAG) is a fully-documented investigation
that hit a genuine platform gap and doesn't run today — **step 9 (native AI
Agent token exchange / STS) is the one that actually works end-to-end** and
is what HR uses in the running code; if you only need one working
real-user-context mechanism, skip straight to §9.

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

Expect a "Receipts" panel confirming all four connections (the CLI's
default set — Kudos Wall, the 5th resource, is opt-in only via the
Streamlit UI's checkboxes, see §12/§13), followed by the narrated
briefing. If a connection fails, the receipts panel tells you which one
and the traceback tells you why — it's a short pipeline.

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

> **Correction (see §12):** point 6 below concludes the resource-side
> catalog integration ("XAA Resource App") doesn't exist on this tenant.
> That conclusion was wrong — it exists as an already-installed app
> (**Todo0 — Cross App Access (XAA) Sample Resource App**, paired with
> **Agent0 — Cross App Access (XAA) Sample Requesting App**), just never
> enabled. §12 has the corrected, working recipe (renamed to "Kudos Wall"
> for this demo). This section is kept as-is below because the *investigation
> steps* (1–5, 7) are still accurate and useful — only the point-6 conclusion
> was incomplete.

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

**Where the code stands:** the ID-JAG implementation (steps 1–5 above,
`_get_id_jag()`/`get_xaa_token_for_user()`) was removed from `okta_auth.py`
once §9 below produced a genuinely working alternative — see git history
(commits around 2026-07-21) if you need to resurrect it once the
resource-app catalog integration becomes available on this org. The
logic was ~30 lines; nothing about it was wrong, it was just blocked.

## 9. Okta's native AI Agent token exchange (STS) — this one actually works

While chasing XAA, the user found a completely different, native Okta
feature under **Directory → Resource Servers** / **Directory → MCP
Servers** / **Directory → AI Agents → Credentials**. This is *not* the
IETF ID-JAG protocol — different token type
(`urn:okta:params:oauth:token-type:oauth-sts`), different client
authentication (a `private_key_jwt` assertion signed by the **AI Agent's
own key pair**, not any app's client_secret), and it's fully self-service
on this org. This is what `main.py`/`okta_auth.py` use for HR today.

### Console setup

1. **Directory → Resource Servers → Add resource server**:
   - Step 1 (Register resource server): name it, and set **Resource
     URL** to the backend's actual base URL (e.g. `http://localhost:8001`
     for `hr-system-mcp`). You can't change this URL later without
     deleting and recreating the entry.
   - Step 2 (Register authorization server): **Authorize Endpoint URL**
     and **Token Endpoint URL** — point these at an *existing* custom
     Okta authorization server's endpoints (reuse the one built in step 3
     of this doc, e.g. `https://{org}/oauth2/{auth_server_id}/v1/authorize`
     and `.../v1/token`). This resource server doesn't need its own new
     authorization server — it can broker through one you already have.
   - Step 3 (Configure client credentials): give this a name, and supply
     an *existing* confidential OAuth app's `client_id`/`client_secret`
     (a normal user-facing app works fine — we used the "front-door" app
     from step 5) plus a scope (e.g. `hr.read`). This is what identity
     Okta uses to broker the authorization_code flow against the
     authorization server from the previous step.
   - There's a separate, parallel **"MCP Servers"** menu item for
     backends that literally speak MCP JSON-RPC (name/description/URL,
     then the same style of pre-registered confidential
     `authorization_code` client + scope, per
     `help.okta.com/.../ai-agent-mcp-server.htm`) — we didn't end up using
     it (used the generic Resource Server path instead), but it's
     probably the more precisely-correct option for a true MCP backend
     and looked like it needs fewer steps (no separate "register
     authorization server" step). Worth trying first next time.
2. **Directory → AI Agents → your agent → Credentials tab → Add public
   key**: click "Generate new key" and let Okta create the RSA keypair.
   **Copy the private key JSON immediately — it's shown exactly once.**
   The **AI agent ID** shown on that same page (not any app's client_id)
   is the "client" identity used for the token-exchange call.
3. **Directory → AI Agents → your agent → Resource connections → Add
   resource connection → resource type "Application" → "Custom resource
   server"**: pick the Resource Server + client-credentials pair from
   step 1. This generates a **Resource indicator**
   (`orn:okta:idp:{orgId}:client-auth-settings:{id}`) — this exact string
   is the `resource` parameter for the runtime call below.

### Runtime flow (implemented in `okta_auth.py:get_sts_token_for_user`)

1. Get a real `id_token` via normal Authorization Code login through the
   app linked to the AI Agent's own registration (its "Application"
   field — see step 5 earlier; we call this the front-door app).
2. Build a `private_key_jwt` client assertion: `iss`/`sub` = the AI Agent
   ID, `aud` = the org token endpoint (`https://{org}/oauth2/v1/token`),
   `RS256`, `kid` matching the uploaded public key, short `exp`, random
   `jti`.
3. `POST https://{org}/oauth2/v1/token` with `grant_type=urn:ietf:params:oauth:grant-type:token-exchange`,
   `requested_token_type=urn:okta:params:oauth:token-type:oauth-sts`,
   `subject_token=<id_token>`, `subject_token_type=urn:ietf:params:oauth:token-type:id_token`,
   `client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer`,
   `client_assertion=<the signed JWT>`, `resource=<the resource
   indicator>`.
4. **First call per user returns `400` with `error=interaction_required`
   and an `interaction_uri`** — unlike XAA, STS *does* require one-time
   user consent. Redirect the user there; after they grant access, retry
   the exact same call and it succeeds with a real `access_token`.

The resulting access token is an ordinary token from the underlying
custom authorization server, with claims like:
```json
{"iss": "https://{org}/oauth2/{auth_server_id}", "aud": "api://...",
 "cid": "<front-door app client_id>", "uid": "...", "sub": "user@example.com",
 "scp": ["hr.read"]}
```
Both `cid` (the agent/app identity) **and** `sub`/`uid` (the real end
user) are present — genuine chain of custody in one token. It needs
**zero changes** to a resource server that already validates tokens from
that authorization server, since it's the same issuer/audience/scope
shape as pattern 1 (`client_credentials`) — only how it got minted
differs.

### Gotchas

- The consent redirect's actual `redirect_uri` is an **Okta-owned URL**
  (`https://{org}/oauth2/v1/sts/callback`), not anything you choose — and
  it must be added to the *front-door app's* registered redirect URIs
  like any other. The first attempt fails with `400: 'redirect_uri'
  parameter must be a Login redirect URI in the client app settings:
  <link to that app>` — the browser's address bar at the moment of that
  error shows the exact attempted `redirect_uri` if you need to confirm
  it (`https://{org}/oauth2/v1/authorize?...&redirect_uri=https%3A%2F%2F{org}%2Foauth2%2Fv1%2Fsts%2Fcallback&...`).
- Once that's fixed, expect `access_denied: Policy evaluation failed for
  this request` — the resource's authorization-server **policy** doesn't
  yet allow the front-door app's `client_id` + the `authorization_code`
  grant type (it only had `client_credentials`/`jwt-bearer` for other
  clients). Add both the client and the grant type to the existing
  policy/rule, the same way as step 3 earlier in this doc.
- The `dataHandle` query param in `interaction_uri` is single-use — if a
  request against it fails (e.g. the redirect_uri issue above), get a
  fresh `interaction_uri` by calling the token-exchange endpoint again
  rather than retrying the same URL, even with parameters "fixed" by
  hand (we got a `403 Access Forbidden` doing that).
- If an app was newly created via the Apps API rather than through the
  console, double check its `redirect_uris`/`grant_types` are what you
  expect — GET responses for some catalog app types don't echo back
  `settings.oauthClient` at all even when the values did apply
  successfully on PUT (seen with the `test-cwo-app` type during the XAA
  investigation above; harmless but confusing when verifying).

## 10. Same STS mechanism via the "MCP Server" resource type (Ticketing)

Sections 3 and 9 registered HR as a **Resource Server** — a generic,
protocol-agnostic resource where you manually tell Okta the authorize/token
endpoints. Okta for AI Agents has a second resource type, **MCP Server**,
that assumes the backend speaks the Model Context Protocol and
**auto-discovers** its protecting authorization server instead of you
entering it by hand. We applied this second pattern to Ticketing so the
demo shows both resource-registration styles feeding the exact same
runtime code path (`get_sts_token_for_user()`).

### MCP Server vs Resource Server — the actual difference

|  | Resource Server (HR) | MCP Server (Ticketing) |
|---|---|---|
| Backend contract assumed | None — any HTTP API | Model Context Protocol (`tools/list`, `tools/call`) |
| How Okta learns the authorization server | You type in the authorize/token endpoints yourself | Okta calls the resource's own `/.well-known/oauth-protected-resource` (RFC 9728) and reads `authorization_servers` from the response |
| Reachability requirement | None — Okta only stores the URL as metadata, never calls it | Okta's cloud must be able to reach the MCP server live, at registration time, to run discovery — a local server needs a public tunnel |
| Runtime token mechanism | Identical: `urn:ietf:params:oauth:grant-type:token-exchange` → `oauth-sts` via `private_key_jwt` | Identical |
| Resulting token shape | Identical (`cid` + `sub`/`uid` both present) | Identical |

In short: this is a **registration-time and discovery-time** distinction
only. Once both are registered, `okta_auth.get_sts_token_for_user()` is the
same function call for either resource — see the in-app "❓ MCP Server vs
Resource Server" popover on the briefing agent's front door for the
short version colleagues see live.

### Step-by-step: adding real auth to a previously-unauthenticated MCP server

`ticketing-system-mcp` (like the other sample servers) shipped with **no
real token validation** despite its README implying one. Before wiring it
into O4AA, add validation modeled on `hr-system-mcp`:

1. Copy the validator module:
   `mcp-servers/hr-system-mcp/auth/okta_validator.py` and `auth/__init__.py`
   → `mcp-servers/ticketing-system-mcp/auth/`. It's generic — reads
   `OKTA_DOMAIN` / `OKTA_AUTHORIZATION_SERVER_ID` / `OKTA_AUDIENCE` /
   `OKTA_REQUIRED_SCOPES` from the environment and validates the bearer
   JWT's signature, issuer, audience, and scopes.
2. Add a `.env` in `ticketing-system-mcp/` with those four values (the
   authorization server ID and audience come from the auth server you'll
   create in step 5 below — this mirrors §3's per-resource auth server
   pattern, just for Ticketing instead of HR).
3. Add `httpx`, `pyjwt`, `python-dotenv` to `requirements.txt` and
   `load_dotenv()` at the top of `main.py`.
4. In the `tools/call` branch of the HTTP handler, extract
   `request.headers.get("Authorization")` and call
   `await validate_authorization_header(auth_header)` before dispatching
   to any tool; return a JSON-RPC `-32001` error if it comes back falsy.
   (`tools/list` and `initialize` stay unauthenticated — same as MCP
   convention, since capability discovery isn't a protected action.)
5. Add the RFC 9728 discovery route the MCP Server registration needs
   (see next section) — a plain Starlette route returning which
   authorization server protects this resource:
   ```python
   async def protected_resource_metadata(request: Request):
       return JSONResponse({
           "resource": str(request.base_url).rstrip("/"),
           "authorization_servers": ["https://{org}/oauth2/{auth_server_id}"],
       })
   app.routes.append(Route("/.well-known/oauth-protected-resource",
                            protected_resource_metadata, methods=["GET"]))
   ```

### Step-by-step: registering the MCP Server in Okta

1. **Create (or reuse) the custom authorization server** that will protect
   this resource — same as §3, with an audience like
   `api://hackathon-ticketing-resource` and a `ticketing.read` scope. Grant
   types on the client policy: this resource only needs
   `authorization_code` (real user context) for the STS flow — there's no
   `client_credentials` fallback for Ticketing, unlike HR.
2. **Expose the MCP server publicly.** Okta's registration wizard performs
   a *live* reachability + discovery check against the URL you give it —
   unlike Resource Server registration, which never calls your endpoint.
   For a server running on `localhost`, start a tunnel:
   ```bash
   ngrok http 8004
   ```
   Use the `https://*.ngrok-free.app` URL (not `localhost`) when
   registering.
3. In Okta admin console: **Applications → AI Agents (or Resource
   Connections) → Add MCP Server**. Enter the ngrok base URL. Okta fetches
   `/.well-known/oauth-protected-resource` from it and should show the
   authorization server(s) it discovered, plus a **Scopes** field
   populated from that authorization server.
   - If you see **"The URL provided could not be validated. Make sure the
     URL is reachable and try again"** — the tunnel isn't up, or the
     discovery route returned something other than 200/JSON. Confirm with
     `curl https://<ngrok-url>/.well-known/oauth-protected-resource`
     first.
   - If you see **"No authorization servers were found"** even after the
     discovery endpoint is live and correct — **discovery only runs once,
     at creation time, not on edit.** Delete the half-created MCP Server
     entry and create a fresh one; don't try to fix it in place.
4. Once saved, the MCP Server resource shows an **ORN**
   (`orn:okta:idp:{app_id}:client-auth-settings:{resource_id}`) — this is
   the `resource_indicator` value `resources.py` needs, exactly like the
   HR resource's ORN from §9.
5. **Link the resource to the AI Agent** in Universal Directory the same
   way as HR/Finance were linked in §5, so the agent's `private_key_jwt`
   assertion is trusted to request tokens for it.
6. If an older/duplicate authorization-server link exists on the resource
   (e.g. a stray link to another auth server's audience from an earlier
   attempt), deactivate it so only the correct one is active — Okta allows
   multiple links but only one should be live per resource in this demo.

### Wiring it into the agent

- `resources.py`: `ticketing.resource_indicator` = the ORN from step 4
  above; `connection_type` = `"AI Agent token exchange via MCP Server
  (OAuth STS)"` (distinct label from HR's, purely for the receipts UI —
  the runtime call is identical).
- `main.py`'s `ticketing_client()` calls `get_sts_token_for_user()` with no
  `client_credentials` fallback branch (unlike `hr_client()`), since this
  resource's authorization server policy doesn't allow that grant type. If
  there's no logged-in user (e.g. CLI mode), it returns `None` and
  `gather_briefing_data()` skips the ticket-related tool calls entirely
  rather than failing.
- Same `ConsentRequired` / `interaction_uri` one-time-consent handling as
  HR applies here — each resource requires its own separate user consent
  the first time.

## 11. Mapping this demo to Okta's broader O4AA pattern catalog

Okta's internal Lucid deck "AI Use Cases/Patterns" catalogues **7 distinct
agentic-identity patterns** (confirmed by reading the deck directly):

1. 3rd-party agent → 1st-party MCP server (external agents like
   ChatGPT/Gemini/Claude reaching an internal MCP server)
2. **1st-party (internal) agent → internal MCP/API, user-delegated
   (workforce)** — the token carries both agent and real-employee identity
3. Partner/3rd-party agent → MCP or B2B APIs, no end-user
4. **Internal agent → internal API, fully autonomous, no user**
5. Agent-to-agent (A2A) delegation, with and without user context
6. **Internal agent (as MCP client) → 3rd-party MCP server**, registered
   in Okta's MCP Server Registry, using STS Brokered Consent to store/
   retrieve tokens
7. Fine-Grained Authorization (FGA) for tool/agent permission scoping

This demo's five resources map onto that catalog like this:

| Resource | Pattern | Why |
|---|---|---|
| HR (Resource Server + STS, §9) | **Pattern 2** | Internal agent, real logged-in employee, token carries both `cid` and `sub`/`uid` |
| Ticketing (MCP Server + STS, §10) | **Pattern 6's mechanics** | Same user-delegation as HR, but via Okta's auto-discovering MCP Server registration instead of a hand-configured Resource Server. Note: pattern 6's original example is an internal agent reaching an *external* SaaS MCP server (e.g. Atlassian) — here the same registration/discovery mechanism is applied to an *internal* resource instead |
| Finance (`client_credentials`, §3) | **Pattern 4** | App-only credential, no human in the loop |
| Analytics (OPA vault, §4) | **Credential Vault Broker** building block (part of pattern 1, not a full pattern of its own) | Legacy static-key resource, no OAuth at all |
| Kudos Wall (real XAA/ID-JAG, §12 — currently paused) | **True XAA** (the actual `draft-ietf-oauth-identity-assertion-authz-grant` protocol) | Admin-defined access, no per-user consent — appropriate for low-sensitivity data. The resource runs its **own** authorization server, unlike every other row here |

In the Streamlit UI, each resource's "Details" expander (in the "Which
systems should the agent connect to?" section) shows this mapping plus a
small sequence diagram (generated fresh via the Lucid MCP integration —
`assets/patterns/*.png` — not copied from the existing deck's canvas).

## 12. Real Cross-App Access, actually working — Kudos Wall (currently paused)

§8 concluded real XAA was blocked by a missing resource-side catalog
integration. That conclusion was wrong. **Agent0 — Cross App Access (XAA)
Sample Requesting App** and **Todo0 — Cross App Access (XAA) Sample
Resource App** — Okta's own official XAA demo pair — were already
installed and linked (Manage Connections) on `ligalac.okta.com`. Nobody
had ever gone looking at the Applications list for them; the catalog
*search* API genuinely doesn't index these entries (confirmed in §8), but
that only means you can't find them by searching to *install* them — it
says nothing about whether an instance already exists. **Lesson: check the
Applications list for already-installed instances before concluding a
catalog integration "doesn't exist" from a failed search.** (See
`debugging_unfamiliar_admin_consoles` guidance in the private SE
notes/memory — this is a repeat of that pattern.)

We renamed them to match this project's convention:
- **Agent0 → "Monday Briefing Agent - XAA Requester"**
- **Todo0 → "Monday Briefing Agent - Kudos Wall"**

### Why XAA needs a self-hosted resource authorization server

Walking Todo0/Kudos Wall's **Resource Server → Cross-app access (XAA)**
tab live revealed the actual architecture: an **Enable** checkbox (was
off) plus an **Issuer URL** field — "the base URL of this app's
authorization server, used by Okta to direct token verification
requests." Unlike every other pattern in this demo, **the resource runs
its own authorization server** — Okta only mints the ID-JAG; it never
validates the final access token itself. This matches the "Own Auth
Server" pattern referenced in §8 point 8.

### What we built: `mcp-servers/kudos-wall-mcp/`

One Starlette process serving three routes on one port (8005):
- **`POST /oauth2/kudos-wall/v1/token`** — the jwt-bearer redemption
  endpoint Kudos Wall's Issuer URL points at. Verifies the incoming
  ID-JAG's signature against **Okta's org-level JWKS**
  (`https://{OKTA_DOMAIN}/oauth2/v1/keys`), checks `aud` matches our own
  issuer and `exp`, then mints a **self-signed** access token (own
  generated RSA keypair) with `sub` = the delegated user and `act.sub` =
  the requesting client — the same chain-of-custody claim shape as STS,
  just via a completely different protocol. Per Okta's own XAA docs: this
  endpoint must **not** accept a `scope` param — it's already embedded in
  the ID-JAG from step 1.
- **`GET /oauth2/kudos-wall/.well-known/oauth-authorization-server`** +
  **`GET /oauth2/kudos-wall/v1/keys`** — deliberately shaped like Okta's
  own discovery URL convention so the **exact same, unmodified**
  `auth/okta_validator.py` used by every other sample server validates
  our self-issued tokens too — just point its `OKTA_DOMAIN` at our own
  ngrok host and `OKTA_AUTHORIZATION_SERVER_ID` at `kudos-wall`.
- **`POST /mcp`** — the actual `list_kudos`/`give_kudos` tools, gated by
  that reused validator.

Exposed via `ngrok http 8005` (same reachability requirement as the MCP
Server pattern in §10, since the resource's own AS also needs to be
callable — both by us, for redemption, and potentially by Okta for the
XAA "app support" check on save).

### Restored client code: `okta_auth.py`

`_get_id_jag()` / `get_xaa_token_for_user()` — recovered from git history
(`git show bb3745a:briefing-agent/okta_auth.py`, never actually broken,
just removed from the working tree once §9's STS became the fallback
plan) and adapted so the redemption step targets our own resource AS
instead of an Okta-hosted one. Authenticates as Agent0 using plain
`client_id`/`client_secret` in the form body (`XAA_REQUESTER_CLIENT_ID`/
`_SECRET`) — **not** the AI Agent Workload Principal identity
(`private_key_jwt`) used for STS. These are two unrelated identities;
don't conflate them.

### The anti-confused-deputy gotcha: a second login flow

Real XAA enforces that the `subject_token` (the id_token) must be issued
**by the same client performing the exchange** — reusing the main app
login's id_token (issued by "Front Door") fails with `'subject_token' is
invalid'`. Fix: `auth.py` has a **second**, separate, on-demand login flow
through Agent0 specifically (`build_agent0_authorize_url()` /
`exchange_agent0_code_for_id_token()`), triggered only when Kudos Wall is
selected. Register the *same* `OKTA_LOGIN_REDIRECT_URI` as a Login
redirect URI on Agent0 too — the same literal URL can be registered on
multiple Okta apps.

**Related gotcha, easy to miss:** Streamlit's `st.session_state` does
**not** reliably survive a full-page round trip to an external domain and
back. Invisible on the *first* login (there's no session to lose), very
visible on this *second* external round trip (session state silently
resets, and the returning Agent0 callback gets misread as a failed Front
Door login). Fixed by backing the logged-in user (and the Agent0
id_token) with the same kind of module-level global already used for the
pending-`state` CSRF trackers — see `auth.save_user()`/`get_saved_user()`
and `save_agent0_id_token()`/`get_saved_agent0_id_token()`.

### Current status: paused

We got as far as a real, specific error that's genuinely different from
§8's: `invalid_target: The resource app is not completely configured or
user is not assigned to the app` — but this time, **the user IS assigned**
and **XAA IS enabled with a correct Issuer URL**. The remaining gap is on
**Kudos Wall's "Okta API Scopes" tab** — a custom scope (`kudos.read`)
likely needs to be explicitly declared there before Okta will embed it in
an ID-JAG for this resource, and we haven't finished that config. Resume
by declaring the scope there and retrying; the client code and resource
server are already fully wired and don't need further changes.

## 13. Streamlit UI features

- **Per-resource selection with inline details** (not a separate
  post-generation "receipts" section): the "Which systems should the
  agent connect to?" checkboxes each show the `connection_type` and a
  "Details" expander with the mechanism description and pattern diagram —
  all static, so it renders before you even click Generate.
- **Live Okta ↔ MCP call trace** (`call_log.py`, sidebar): every HTTP call
  the agent makes during a run — Okta token endpoints, the MCP servers'
  `/mcp` calls — logged with method/URL/request/response. Secrets
  (`client_secret`, vaulted API keys) are fully redacted; tokens are
  truncated with their **claims decoded alongside** (unverified, display
  only) — this is the single best "prove it" artifact in the whole demo,
  since it shows the actual `cid`/`sub`/`act` claims live. Cleared at the
  start of each "Generate" click; a "Clear trace" button resets it
  manually. `logged_post()`/`logged_get()` in `call_log.py` are drop-in
  replacements for `httpx.post()`/`httpx.get()` used throughout
  `okta_auth.py`, `auth.py`, and `mcp_client.py`.
- **Language selector** (`i18n.py` + a `st.selectbox` at the top of the
  sidebar): switches the *entire* UI between English (US), Spanish
  (Latin America), and Brazilian Portuguese — including the long Why/
  Requires explanations in each resource's "Details" popover, the
  MCP-vs-Resource-Server writeup, and every consent/warning/info message.
  Protocol/product terms (`OAuth`, `client_credentials`, `private_key_jwt`,
  `MCP`, `XAA`, `ID-JAG`, `Resource Server`, etc.) are deliberately left
  untranslated in all three languages — a technical audience expects those
  as-is. The selected language is also passed into `main.narrate()`, so
  Claude writes the generated briefing itself in that language, not just
  the surrounding UI. Selection lives in `st.session_state["lang"]`
  (`"en"` / `"es"` / `"pt-BR"`) for the duration of the session; nothing is
  persisted across restarts. To add a string: add a key to `TEXT` (or a
  field to `RESOURCE_TEXT` for per-resource content) in `i18n.py` with all
  three languages, then reference it via `t("key")` / `rt(resource_key,
  "field")` in `app.py`.
- **Streamlit's built-in menu is trimmed to "minimal"**
  (`.streamlit/config.toml`, `[client] toolbarMode = "minimal"`) — this
  hides the whole hamburger menu (Deploy, Rerun, **Print**, **Record a
  screencast**, Settings, About), not just the Deploy button. This config
  is only read at process startup, so changing it requires a full restart
  (`streamlit run app.py ...`), not just a rerun/refresh.
