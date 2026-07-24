"""Shared in-memory trace of every HTTP call this agent makes to Okta's
authorization servers and the backend MCP servers -- powers the Streamlit
sidebar's live "what actually happened" panel. Secrets are redacted;
tokens are truncated but their claims are decoded (unverified -- for
display only, not a substitute for real signature verification, which
happens separately wherever a token is actually consumed)."""

import base64
import json
import time

import httpx

_log: list[dict] = []

_REDACT_KEYS = {"client_secret", "key_secret"}
# These carry a JWT worth showing decoded claims for -- everything else
# (scope, grant_type, client_id, ...) is shown as-is, it's not sensitive.
_TOKEN_KEYS = {
    "client_assertion", "subject_token", "assertion",
    "access_token", "id_token",
}


def clear() -> None:
    global _log
    _log = []


def get_log() -> list[dict]:
    return _log


def decode_jwt_claims(token: str) -> dict | None:
    """Best-effort, UNVERIFIED decode of a JWT's payload segment, purely
    for human-readable display in the trace panel (and, via
    okta_auth.token_expiry_ts, the Details popover's token-TTL readout).
    Not a substitute for real signature verification, which happens
    separately wherever a token is actually consumed."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return None


def _redact_value(key: str, value):
    if not isinstance(value, str):
        return value
    if key in _REDACT_KEYS:
        return "***REDACTED***"
    if key == "authorization" and value.lower().startswith("ssws "):
        # Okta's own admin-API auth scheme (org SSWS token) -- opaque, not
        # a JWT, so there are no claims to decode; unlike Bearer below,
        # fully redact rather than partially showing it. This is the one
        # credential in the whole app with org-wide admin scope, so it
        # gets the strictest treatment.
        return "***REDACTED***"
    if key in _TOKEN_KEYS or (key == "authorization" and value.lower().startswith("bearer ")):
        prefix = "Bearer " if key == "authorization" else ""
        raw = value[len(prefix):] if prefix else value
        shortened = f"{raw[:16]}...{raw[-8:]}" if len(raw) > 30 else raw
        entry = {"value": prefix + shortened}
        claims = decode_jwt_claims(raw)
        if claims:
            entry["decoded_claims"] = claims
        return entry
    return value


def _redact_dict(d: dict) -> dict:
    return {k: _redact_value(k, v) for k, v in d.items()}


def record(label: str, method: str, url: str, kwargs: dict, resp: httpx.Response) -> None:
    request = {}
    if "data" in kwargs:
        request = _redact_dict(dict(kwargs["data"]))
    elif "json" in kwargs:
        request = _redact_dict(dict(kwargs["json"]))
    headers = dict(kwargs.get("headers") or {})
    for hk in list(headers.keys()):
        if hk.lower() == "authorization":
            headers[hk] = _redact_value("authorization", headers[hk])
        elif hk.lower() == "x-api-key":
            headers[hk] = "***REDACTED***"
    auth = kwargs.get("auth")
    if auth:
        request["_client_auth"] = {"client_id": auth[0], "client_secret": "***REDACTED***"}

    try:
        response_body = resp.json()
        if isinstance(response_body, dict):
            response_body = _redact_dict(response_body)
    except ValueError:
        response_body = resp.text[:500]

    _log.append({
        "time": time.strftime("%H:%M:%S"),
        "label": label,
        "method": method,
        "url": url,
        "request": request,
        "headers": headers,
        "status_code": resp.status_code,
        "response": response_body,
    })


def logged_post(label: str, url: str, **kwargs) -> httpx.Response:
    resp = httpx.post(url, **kwargs)
    record(label, "POST", url, kwargs, resp)
    return resp


def logged_get(label: str, url: str, **kwargs) -> httpx.Response:
    resp = httpx.get(url, **kwargs)
    record(label, "GET", url, kwargs, resp)
    return resp
