"""Okta OIDC login for the Streamlit front end.

Uses the org authorization server (not a custom one -- the XAA Requester
app type rejects those with "This client cannot use a custom authorization
server") and the XAA Requester app itself as the login client, so the
resulting id_token's `aud` matches the app that will use it as the
subject_token for real Cross-App Access -- Authorization Code flow,
confidential client.
"""

import os
import secrets

import httpx

# Org authorization server endpoints have no {authServerId} path segment,
# unlike custom authorization servers (e.g. "default").
ORG_AUTH_BASE = "/oauth2/v1"

# Tracks the single in-flight login's state across the external redirect to
# Okta and back. st.session_state doesn't reliably survive that round trip
# (the browser fully leaves the page), but this module stays loaded in the
# same process for as long as `streamlit run` is up -- fine for a
# single-user local demo, not a substitute for real session storage in a
# multi-user deployment.
_pending_state = None


def _domain() -> str:
    return os.environ["OKTA_DOMAIN"]


def build_authorize_url() -> str:
    global _pending_state
    _pending_state = secrets.token_urlsafe(16)
    params = {
        "client_id": os.environ["OKTA_LOGIN_CLIENT_ID"],
        "response_type": "code",
        "scope": "openid profile email",
        "redirect_uri": os.environ["OKTA_LOGIN_REDIRECT_URI"],
        "state": _pending_state,
    }
    return f"https://{_domain()}{ORG_AUTH_BASE}/authorize?" + httpx.QueryParams(params).__str__()


def consume_pending_state(received_state: str) -> bool:
    """Returns True iff received_state matches the last issued state, then clears it."""
    global _pending_state
    matched = _pending_state is not None and received_state == _pending_state
    _pending_state = None
    return matched


def exchange_code_for_userinfo(code: str) -> dict:
    """Returns userinfo plus the raw id_token under "_id_token" -- the id_token
    is the subject_token real Cross-App Access needs to act on behalf of this
    user (see okta_auth.get_xaa_token_for_user)."""
    token_resp = httpx.post(
        f"https://{_domain()}{ORG_AUTH_BASE}/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": os.environ["OKTA_LOGIN_REDIRECT_URI"],
        },
        auth=(os.environ["OKTA_LOGIN_CLIENT_ID"], os.environ["OKTA_LOGIN_CLIENT_SECRET"]),
        timeout=10,
    )
    token_resp.raise_for_status()
    tokens = token_resp.json()

    userinfo_resp = httpx.get(
        f"https://{_domain()}{ORG_AUTH_BASE}/userinfo",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        timeout=10,
    )
    userinfo_resp.raise_for_status()
    return {**userinfo_resp.json(), "_id_token": tokens["id_token"]}
