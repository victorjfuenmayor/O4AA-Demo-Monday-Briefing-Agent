"""Credential brokering for the briefing agent.

Four O4AA resource-connection mechanisms, one function each:

- get_sts_token_for_user(): Okta's native AI Agent token exchange. The
  agent authenticates with a private_key_jwt client assertion signed by
  the AI Agent's own key pair (generated during AI Agent registration --
  see AI_AGENT_ID/AI_AGENT_PRIVATE_KEY_JWK), exchanges the logged-in
  user's id_token for an access token scoped to a specific resource
  connection. Unlike client_credentials, the resulting token carries the
  real end user's identity (sub/uid) alongside the agent's own (cid) --
  genuine chain of custody. Because the token makes an assertion about a
  specific real person, Okta requires that person to explicitly approve it
  once per resource (raises ConsentRequired the first time; see
  interaction_uri) -- this is the one mechanism here that ever shows a
  "Grant access" prompt. Used for hr-system-mcp (registered as a Resource
  Server) and ticketing-system-mcp (registered as an MCP Server -- same
  mechanism, different registration/discovery path; see SETUP.md §10).

- get_xaa_token_for_user() / _get_id_jag(): real Cross-App Access (the
  IETF draft-ietf-oauth-identity-assertion-authz-grant / ID-JAG protocol),
  a genuinely different mechanism from STS above -- admin-defined access
  instead of per-user consent, and the resource runs its OWN authorization
  server rather than one of Okta's. Used for kudos-wall-mcp. See SETUP.md
  §12 for the full recipe (this was blocked for a long time on the
  incorrect assumption that the tenant lacked resource-app support --
  turned out the sample apps were already installed, just never enabled).

- get_client_credentials_token(): plain OAuth2 client_credentials against
  a per-resource Okta custom authorization server -- app-only, no user
  context, so there's no user identity to assert and never a consent
  prompt. Used for finance-system-mcp.

- get_vaulted_secret(): legacy/static-secret resources — the API key is
  vaulted in Okta Privileged Access (OPA) and fetched just-in-time via OPA's
  Reveal a Secret flow (client generates an ephemeral RSA keypair, OPA
  re-encrypts the secret with it, client decrypts locally) rather than
  living in agent config. No user identity involved here either, so no
  consent prompt. Used for analytics-system-mcp.
"""

import json
import os
import time
import uuid
import httpx
from jwcrypto import jwe, jwk
from jwcrypto import jwt as jwcrypto_jwt

from call_log import logged_post


class ConsentRequired(Exception):
    """Raised by get_sts_token_for_user() the first time a given user grants
    a given resource. resource_label/connection_type are filled in by the
    caller (main.py) after the fact, since this function only knows the
    resource_indicator, not the human-readable resource it belongs to --
    the UI uses them to explain *which* pattern is asking for consent."""

    def __init__(self, interaction_uri: str, resource_label: str | None = None, connection_type: str | None = None):
        self.interaction_uri = interaction_uri
        self.resource_label = resource_label
        self.connection_type = connection_type
        super().__init__(f"User consent required for {resource_label or 'resource'}: {interaction_uri}")


def _raise_with_body(resp: httpx.Response):
    if resp.is_error:
        raise httpx.HTTPStatusError(f"{resp.status_code} from {resp.request.url}: {resp.text}", request=resp.request, response=resp)


def _build_client_assertion(token_endpoint: str) -> str:
    """Signs a private_key_jwt client assertion using the AI Agent's own
    key pair (generated during AI Agent registration, RFC 7523)."""
    private_key_jwk = json.loads(os.environ["AI_AGENT_PRIVATE_KEY_JWK"])
    key = jwk.JWK(**private_key_jwk)
    agent_id = os.environ["AI_AGENT_ID"]

    now = int(time.time())
    token = jwcrypto_jwt.JWT(
        header={"alg": "RS256", "kid": private_key_jwk["kid"]},
        claims={
            "iss": agent_id,
            "sub": agent_id,
            "aud": token_endpoint,
            "iat": now,
            "exp": now + 300,
            "jti": str(uuid.uuid4()),
        },
    )
    token.make_signed_token(key)
    return token.serialize()


def _get_id_jag(subject_id_token: str, audience: str, scope: str) -> str:
    """Step 1 of real Cross-App Access (XAA): exchange the user's id_token
    for an ID-JAG, scoped to a specific resource authorization server
    (`audience`). Authenticates as the "XAA Requester" app (Agent0),
    Okta's own official XAA sample requesting app -- a plain confidential
    OAuth client (client_id/secret in the form body), not the AI Agent
    Workload Principal identity used by get_sts_token_for_user() below.

    This was blocked for months on the (incorrect) assumption that the
    tenant lacked a resource-side "XAA Resource App" catalog integration.
    It turned out Agent0 + its paired resource app ("Todo0", renamed to
    the Kudos Wall app for this demo) were already installed and linked --
    just never enabled. See SETUP.md §12."""
    domain = os.environ["OKTA_DOMAIN"]
    resp = logged_post(
        "Okta org token endpoint — mint ID-JAG (XAA step 1)",
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


def get_xaa_token_for_user(resource_issuer_url: str, scope: str, subject_id_token: str) -> str:
    """Step 2: redeem the ID-JAG for a resource access token at the
    resource's OWN authorization server -- not one of Okta's custom auth
    servers. `resource_issuer_url` is the Kudos Wall MCP server's own
    issuer (see mcp-servers/kudos-wall-mcp/xaa_resource_as.py), the same
    value configured as that app's "Issuer URL" in the Okta console.
    Per Okta's own XAA docs: do NOT include a scope param here -- it's
    already embedded in the ID-JAG from step 1."""
    id_jag = _get_id_jag(subject_id_token, resource_issuer_url, scope)

    resp = logged_post(
        "Kudos Wall's own authorization server — redeem ID-JAG (XAA step 2)",
        f"{resource_issuer_url}/v1/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": id_jag,
        },
        timeout=10,
    )
    _raise_with_body(resp)
    return resp.json()["access_token"]


def get_sts_token_for_user(subject_id_token: str, resource_indicator: str) -> str:
    domain = os.environ["OKTA_DOMAIN"]
    token_endpoint = f"https://{domain}/oauth2/v1/token"
    assertion = _build_client_assertion(token_endpoint)

    resp = logged_post(
        "Okta org token endpoint — AI Agent token exchange (OAuth STS)",
        token_endpoint,
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "requested_token_type": "urn:okta:params:oauth:token-type:oauth-sts",
            "subject_token": subject_id_token,
            "subject_token_type": "urn:ietf:params:oauth:token-type:id_token",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": assertion,
            "resource": resource_indicator,
        },
        timeout=10,
    )
    if resp.status_code == 400 and resp.json().get("error") == "interaction_required":
        raise ConsentRequired(resp.json()["interaction_uri"])
    _raise_with_body(resp)
    return resp.json()["access_token"]


def get_client_credentials_token(auth_server_id: str, scope: str) -> str:
    domain = os.environ["OKTA_DOMAIN"]
    client_id = os.environ["OKTA_AGENT_CLIENT_ID"]
    client_secret = os.environ["OKTA_AGENT_CLIENT_SECRET"]

    token_url = f"https://{domain}/oauth2/{auth_server_id}/v1/token"
    resp = logged_post(
        "Okta custom authorization server — client_credentials",
        token_url,
        data={"grant_type": "client_credentials", "scope": scope},
        auth=(client_id, client_secret),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _opa_service_token() -> str:
    resp = logged_post(
        "Okta Privileged Access — service token",
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
    resp = logged_post(
        "Okta Privileged Access — reveal vaulted secret",
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
