"""
Kudos Wall's own authorization server -- the resource-side half of real
Cross-App Access (XAA). Unlike every other sample MCP server in this repo
(which is protected by one of Okta's own custom authorization servers),
XAA requires the resource to run its OWN authorization server: Okta mints
an ID-JAG scoped to *this* issuer, and this module is what redeems it.

Two responsibilities:
1. Verify an incoming ID-JAG was really signed by Okta's org authorization
   server, for the audience we expect (our own issuer URL), and hasn't
   expired.
2. Mint our own short-lived access token (self-signed) carrying both the
   delegated user's identity (sub) and the requesting agent's identity
   (act.sub) -- the XAA chain-of-custody claim pair.
"""

import json
import os
import time
import uuid

import httpx
import jwt as pyjwt
from jwcrypto import jwk
from jwcrypto import jwt as jwcrypto_jwt

ISSUER_PATH = "/oauth2/kudos-wall"
RESOURCE_AUDIENCE = "api://kudos-wall"


def _signing_key() -> jwk.JWK:
    return jwk.JWK(**json.loads(os.environ["SIGNING_KEY_JWK"]))


def _issuer_url() -> str:
    return os.environ["PUBLIC_BASE_URL"].rstrip("/") + ISSUER_PATH


def discovery_document() -> dict:
    issuer = _issuer_url()
    return {
        "issuer": issuer,
        "jwks_uri": f"{issuer}/v1/keys",
        "token_endpoint": f"{issuer}/v1/token",
        "grant_types_supported": ["urn:ietf:params:oauth:grant-type:jwt-bearer"],
    }


def jwks_document() -> dict:
    public_jwk = json.loads(_signing_key().export_public())
    return {"keys": [public_jwk]}


def _fetch_okta_jwks(okta_domain: str) -> dict:
    resp = httpx.get(f"https://{okta_domain}/oauth2/v1/keys", timeout=10)
    resp.raise_for_status()
    return resp.json()


def _verify_id_jag(id_jag: str) -> dict:
    """Verifies the ID-JAG was signed by Okta's org authorization server,
    scoped to our issuer, and not expired. Returns its claims.

    Uses OKTA_ORG_DOMAIN (Okta's real domain, e.g. dev-12345.okta.com) --
    deliberately distinct from OKTA_DOMAIN, which auth/okta_validator.py
    reads to discover *our own* issuer for validating the tokens we
    ourselves mint below. Same env var name, two different authorization
    servers, would collide."""
    okta_domain = os.environ["OKTA_ORG_DOMAIN"]

    header = pyjwt.get_unverified_header(id_jag)
    kid = header.get("kid")
    if not kid:
        raise ValueError("ID-JAG missing 'kid' header")

    jwks = _fetch_okta_jwks(okta_domain)
    signing_key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if not signing_key:
        raise ValueError(f"No matching Okta signing key for kid={kid}")

    public_key = pyjwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(signing_key))
    try:
        claims = pyjwt.decode(
            id_jag,
            public_key,
            algorithms=["RS256"],
            audience=_issuer_url(),
            options={"verify_signature": True, "verify_exp": True, "verify_aud": True},
        )
    except pyjwt.InvalidAudienceError:
        raise ValueError(f"ID-JAG audience does not match our issuer ({_issuer_url()})")
    except pyjwt.ExpiredSignatureError:
        raise ValueError("ID-JAG has expired")
    return claims


async def handle_token_redemption(form: dict) -> dict:
    """POST /v1/token -- grant_type=jwt-bearer, assertion=<ID-JAG>. Per
    Okta's own XAA docs, this step must NOT accept a 'scope' parameter --
    the scope is already embedded in the ID-JAG from step 1."""
    if form.get("grant_type") != "urn:ietf:params:oauth:grant-type:jwt-bearer":
        raise ValueError("unsupported grant_type for this endpoint")

    assertion = form.get("assertion")
    if not assertion:
        raise ValueError("missing 'assertion' (the ID-JAG)")

    claims = _verify_id_jag(assertion)

    delegated_user = claims.get("sub")
    requesting_agent = claims.get("cid") or claims.get("client_id") or claims.get("azp") or "unknown-requester"
    scope = claims.get("scope") or claims.get("scp") or "kudos.read"
    if isinstance(scope, list):
        scope = " ".join(scope)

    now = int(time.time())
    access_token = jwcrypto_jwt.JWT(
        header={"alg": "RS256", "kid": json.loads(_signing_key().export_public())["kid"]},
        claims={
            "iss": _issuer_url(),
            "sub": delegated_user,
            "act": {"sub": requesting_agent},
            "aud": RESOURCE_AUDIENCE,
            "scope": scope,
            "iat": now,
            "exp": now + 300,
            "jti": str(uuid.uuid4()),
        },
    )
    access_token.make_signed_token(_signing_key())

    return {
        "access_token": access_token.serialize(),
        "token_type": "Bearer",
        "expires_in": 300,
        "scope": scope,
    }
