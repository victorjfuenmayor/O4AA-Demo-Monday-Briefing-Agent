# Kudos Wall MCP Server (Bonusly-like)

Protected by **real Cross-App Access (XAA)** -- Okta's
`draft-ietf-oauth-identity-assertion-authz-grant` / ID-JAG protocol. Unlike
every other sample MCP server in this repo, this one *is* the resource's
own authorization server: Okta never validates its tokens directly, it
just mints an ID-JAG scoped to this server's issuer, which this server then
redeems for a self-signed access token. See `SETUP.md` §12 in the repo root
for the full console setup (the "Agent0"/"Kudos Wall" app pair, enabling
XAA, the Issuer URL field).

## Endpoints

| Route | Purpose |
|---|---|
| `POST /mcp` | The actual MCP tools (`list_kudos`, `give_kudos`), gated by a bearer token minted by this same server |
| `POST /v1/token` | jwt-bearer redemption -- exchanges an ID-JAG (minted by Okta's org token endpoint) for a resource access token |
| `GET /oauth2/kudos-wall/.well-known/oauth-authorization-server` | Discovery doc for this server's own issuer |
| `GET /oauth2/kudos-wall/v1/keys` | JWKS for the keypair this server signs its own tokens with |

## Quick start

```bash
pip install -r requirements.txt
# .env already has a generated signing key -- fill in OKTA_DOMAIN and
# PUBLIC_BASE_URL once ngrok is running (see SETUP.md §12)
python main.py --http 8005
```

## Why this server looks different from the others

`hr-system-mcp`/`finance-system-mcp`/`ticketing-system-mcp`/
`analytics-system-mcp` are all protected by an Okta-hosted authorization
server -- their `auth/okta_validator.py` points at Okta's own discovery
endpoint. This server's `auth/okta_validator.py` is the exact same code,
unmodified, just pointed at *this server's own* discovery endpoint instead
(`OKTA_DOMAIN` here is our own ngrok host, not Okta's domain) -- because in
real XAA, the resource runs its own authorization server, and Okta's job
is only to mint the ID-JAG, not to validate the final access token.
