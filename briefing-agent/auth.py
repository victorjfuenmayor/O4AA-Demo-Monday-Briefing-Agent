"""Okta OIDC login for the Streamlit front end.

Two separate login flows against the org authorization server
(no {authServerId} segment, unlike custom authorization servers):

1. build_authorize_url() / consume_pending_state() / exchange_code_for_userinfo():
   the main app login, via the Front Door app (OKTA_LOGIN_CLIENT_ID). Its
   id_token is the subject_token for the STS-based connections (HR,
   Ticketing) -- for STS, any app linked to the AI Agent's registration
   works, the id_token's `aud` doesn't have to match a specific client.

2. build_agent0_authorize_url() / consume_agent0_pending_state() /
   exchange_agent0_code_for_id_token(): a SECOND, separate login via the
   XAA Requester app (Agent0, XAA_REQUESTER_CLIENT_ID) -- needed because
   real Cross-App Access enforces an anti-confused-deputy check: the
   subject_token's `aud` must equal the client performing the token
   exchange. Reusing the Front Door-issued id_token for the Kudos Wall
   XAA flow fails with "'subject_token' is invalid" for exactly this
   reason. Register the same OKTA_LOGIN_REDIRECT_URI as a Login redirect
   URI on Agent0 too -- the same literal URL can be registered on multiple
   Okta apps.
"""

import os
import secrets

import httpx

from call_log import logged_get, logged_post

# Org authorization server endpoints have no {authServerId} path segment,
# unlike custom authorization servers (e.g. "default").
ORG_AUTH_BASE = "/oauth2/v1"

# Tracks each in-flight login's state across the external redirect to Okta
# and back. st.session_state doesn't reliably survive that round trip (the
# browser fully leaves the page), but this module stays loaded in the same
# process for as long as `streamlit run` is up -- fine for a single-user
# local demo, not a substitute for real session storage in a multi-user
# deployment. Separate trackers since the two flows can be mid-flight
# independently (Front Door login happens first, Agent0 login later, on
# demand, once Kudos Wall is needed).
_pending_state = None
_agent0_pending_state = None

# Same fragility applies to st.session_state["user"] itself, not just the
# pending-state trackers above: navigating away to Okta and back is a full
# page load, and Streamlit doesn't reliably resume the same session across
# it. That's invisible on the FIRST login (there's no prior session_state
# to lose), but very visible on the SECOND external round trip within the
# same browser tab (the Agent0 login below) -- session_state["user"] goes
# missing, require_login() thinks nobody's logged in, and misreads the
# returning Agent0 code/state as a failed *Front Door* login attempt.
# Mirroring the pending-state trackers' module-global approach fixes it.
_saved_user = None


def save_user(user: dict) -> None:
    global _saved_user
    _saved_user = user


def clear_saved_user() -> None:
    """Must be called on logout -- otherwise require_login() just restores
    the user right back from this cache on the very next rerun."""
    global _saved_user
    _saved_user = None


def get_saved_user() -> dict | None:
    return _saved_user


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
    """Returns userinfo plus the raw id_token under "_id_token" -- used as
    the subject_token for the STS-based connections (HR, Ticketing)."""
    token_resp = logged_post(
        "Okta org token endpoint — Front Door login (authorization_code)",
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

    userinfo_resp = logged_get(
        "Okta org userinfo endpoint",
        f"https://{_domain()}{ORG_AUTH_BASE}/userinfo",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        timeout=10,
    )
    userinfo_resp.raise_for_status()
    return {**userinfo_resp.json(), "_id_token": tokens["id_token"]}


def build_agent0_authorize_url() -> str:
    global _agent0_pending_state
    _agent0_pending_state = secrets.token_urlsafe(16)
    params = {
        "client_id": os.environ["XAA_REQUESTER_CLIENT_ID"],
        "response_type": "code",
        "scope": "openid profile email",
        "redirect_uri": os.environ["OKTA_LOGIN_REDIRECT_URI"],
        "state": _agent0_pending_state,
    }
    return f"https://{_domain()}{ORG_AUTH_BASE}/authorize?" + httpx.QueryParams(params).__str__()


def consume_agent0_pending_state(received_state: str) -> bool:
    global _agent0_pending_state
    matched = _agent0_pending_state is not None and received_state == _agent0_pending_state
    _agent0_pending_state = None
    return matched


# Same session_state fragility as _saved_user above -- back this with a
# module global too, so a later page reload/reconnect doesn't force
# re-doing the Agent0 login on top of everything else.
_saved_agent0_id_token = None


def save_agent0_id_token(token: str) -> None:
    global _saved_agent0_id_token
    _saved_agent0_id_token = token


def get_saved_agent0_id_token() -> str | None:
    return _saved_agent0_id_token


def clear_saved_agent0_id_token() -> None:
    global _saved_agent0_id_token
    _saved_agent0_id_token = None


def exchange_agent0_code_for_id_token(code: str) -> str:
    """Returns just the id_token -- its `aud` is Agent0's client_id, which
    is what real Cross-App Access requires as the subject_token."""
    token_resp = logged_post(
        "Okta org token endpoint — Agent0 login (authorization_code)",
        f"https://{_domain()}{ORG_AUTH_BASE}/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": os.environ["OKTA_LOGIN_REDIRECT_URI"],
        },
        auth=(os.environ["XAA_REQUESTER_CLIENT_ID"], os.environ["XAA_REQUESTER_CLIENT_SECRET"]),
        timeout=10,
    )
    token_resp.raise_for_status()
    return token_resp.json()["id_token"]
