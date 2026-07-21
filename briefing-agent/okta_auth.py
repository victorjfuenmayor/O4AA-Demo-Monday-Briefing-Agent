"""Credential brokering for the briefing agent.

Two O4AA resource-connection types from the O4AA Patterns deck, one function each:

- get_xaa_token(): native XAA — the agent's registered client does an OAuth
  client_credentials grant against a per-resource Okta custom authorization
  server and gets back a short-lived, scoped access token. Used for
  hr-system-mcp and finance-system-mcp, which validate that token themselves.

- get_vaulted_secret(): legacy/static-secret resources — the API key is
  vaulted in Okta Privileged Access (OPA) and fetched just-in-time via OPA's
  Reveal a Secret flow (client generates an ephemeral RSA keypair, OPA
  re-encrypts the secret with it, client decrypts locally) rather than
  living in agent config. Used for ticketing-system-mcp and
  analytics-system-mcp, which only understand a static X-API-Key header.
"""

import json
import os
import httpx
from jwcrypto import jwe, jwk


def get_xaa_token(auth_server_id: str, scope: str) -> str:
    domain = os.environ["OKTA_DOMAIN"]
    client_id = os.environ["OKTA_AGENT_CLIENT_ID"]
    client_secret = os.environ["OKTA_AGENT_CLIENT_SECRET"]

    token_url = f"https://{domain}/oauth2/{auth_server_id}/v1/token"
    resp = httpx.post(
        token_url,
        data={"grant_type": "client_credentials", "scope": scope},
        auth=(client_id, client_secret),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _opa_service_token() -> str:
    resp = httpx.post(
        f"https://{os.environ['OPA_DOMAIN']}/v1/teams/{os.environ['OPA_TEAM_NAME']}/service_token",
        json={"key_id": os.environ["OPA_KEY_ID"], "key_secret": os.environ["OPA_KEY_SECRET"]},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["bearer_token"]


def _opa_reveal_secret() -> dict:
    """Reveals the vaulted OPA secret and returns its decrypted JSON payload."""
    token = _opa_service_token()
    private_key = jwk.JWK.generate(kty="RSA", size=2048, alg="RSA-OAEP-256", use="enc")
    public_jwk = json.loads(private_key.export_public())

    path = (
        f"/resource_groups/{os.environ['OPA_RESOURCE_GROUP_ID']}"
        f"/projects/{os.environ['OPA_PROJECT_ID']}"
        f"/secrets/{os.environ['OPA_SECRET_ID']}"
    )
    resp = httpx.post(
        f"https://{os.environ['OPA_DOMAIN']}/v1/teams/{os.environ['OPA_TEAM_NAME']}{path}",
        json={"public_key": public_jwk},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    resp.raise_for_status()

    envelope = jwe.JWE()
    envelope.deserialize(resp.json()["secret_jwe"], key=private_key)
    return json.loads(envelope.payload.decode())


def get_vaulted_secret(env_fallback: str, opa_key: str) -> str:
    if not os.environ.get("OPA_DOMAIN"):
        # No OPA vault configured for this tenant yet -- fall back to env var.
        # A real deployment must not do this: the key belongs in OPA, fetched
        # just-in-time, never sitting in agent config.
        return os.environ[env_fallback]

    return _opa_reveal_secret()[opa_key]
