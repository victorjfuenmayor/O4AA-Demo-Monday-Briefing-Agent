"""Credential brokering for the briefing agent.

Two O4AA resource-connection types currently in use, one function each:

- get_client_credentials_token(): plain OAuth2 client_credentials against a
  per-resource Okta custom authorization server -- app-only, no user
  context. Used for hr-system-mcp and finance-system-mcp.

- get_vaulted_secret(): legacy/static-secret resources — the API key is
  vaulted in Okta Privileged Access (OPA) and fetched just-in-time via OPA's
  Reveal a Secret flow (client generates an ephemeral RSA keypair, OPA
  re-encrypts the secret with it, client decrypts locally) rather than
  living in agent config. Used for ticketing-system-mcp and
  analytics-system-mcp, which only understand a static X-API-Key header.

get_xaa_token_for_user() below is a complete, correct implementation of
real Cross-App Access (draft-ietf-oauth-identity-assertion-authz-grant) --
not wired into main.py's default flow. It works up through minting the
ID-JAG; redeeming it fails with "The resource app is not completely
configured" because this org's catalog lacks the "XAA Resource App"
integration needed to register HR as a proper XAA resource (confirmed via
developer.okta.com/blog/2026/02/17/xaa-resource-app) -- a genuine platform
gap, not a bug here. See SETUP.md for the full investigation. Revisit if
that catalog integration becomes available on this org.
"""

import json
import os
import httpx
from jwcrypto import jwe, jwk


def get_client_credentials_token(auth_server_id: str, scope: str) -> str:
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


def _raise_with_body(resp: httpx.Response):
    if resp.is_error:
        raise httpx.HTTPStatusError(f"{resp.status_code} from {resp.request.url}: {resp.text}", request=resp.request, response=resp)


def _get_id_jag(subject_id_token: str, audience: str, scope: str) -> str:
    # The requesting-app side of real XAA needs Okta's dedicated
    # cross-app-access-capable app type (catalog integration key
    # "test-cwo-app") -- a generic OIDC app's client_id is rejected by
    # Okta's token-exchange endpoint for requested_token_type=id-jag.
    #
    # Per Okta's own reference client (oktadev/okta-cross-app-access-mcp,
    # packages/id-assert-authz-grant-client), client_id/client_secret go in
    # the form body, not HTTP Basic auth.
    #
    # Per developer.okta.com/blog/2026/02/17/xaa-resource-app: "Only the org
    # authorization server can be used to exchange ID-JAG tokens" -- not a
    # custom authorization server (even one named "default").
    domain = os.environ["OKTA_DOMAIN"]
    resp = httpx.post(
        f"https://{domain}/oauth2/v1/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "requested_token_type": "urn:ietf:params:oauth:token-type:id-jag",
            "subject_token": subject_id_token,
            "subject_token_type": "urn:ietf:params:oauth:token-type:id_token",
            "audience": audience,
            "scope": scope,
            "client_id": os.environ["XAA_REQUESTER_CLIENT_ID"],
            "client_secret": os.environ["XAA_REQUESTER_CLIENT_SECRET"],
        },
        timeout=10,
    )
    _raise_with_body(resp)
    return resp.json()["access_token"]  # the ID-JAG, per RFC 8693 token-exchange response shape


def get_xaa_token_for_user(auth_server_id: str, scope: str, subject_id_token: str) -> str:
    domain = os.environ["OKTA_DOMAIN"]
    audience = f"https://{domain}/oauth2/{auth_server_id}"
    id_jag = _get_id_jag(subject_id_token, audience, scope)

    resp = httpx.post(
        f"{audience}/v1/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": id_jag,
            "client_id": os.environ["XAA_REQUESTER_CLIENT_ID"],
            "client_secret": os.environ["XAA_REQUESTER_CLIENT_SECRET"],
        },
        timeout=10,
    )
    _raise_with_body(resp)
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
