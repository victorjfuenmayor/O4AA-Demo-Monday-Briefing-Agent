"""Monday Briefing Agent.

Assembles an internal ops briefing (org chart, budget status, open tickets,
system health, team shoutouts) from five backend systems, each reached
through a different O4AA-governed resource connection, then asks Claude to
narrate the result.

Usage: python main.py
"""

import os
from dotenv import load_dotenv
from anthropic import Anthropic

from mcp_client import MCPClient
from okta_auth import ConsentRequired, get_client_credentials_token, get_sts_token_for_user, get_vaulted_secret, get_xaa_token_for_user
from resources import RESOURCES

load_dotenv()


def hr_client(receipts: list, subject_id_token: str | None) -> MCPClient:
    r = RESOURCES["hr"]
    if subject_id_token:
        try:
            token = get_sts_token_for_user(subject_id_token, r["resource_indicator"])
        except ConsentRequired as e:
            e.resource_label, e.connection_type = r["label"], r["connection_type"]
            raise
        receipts.append((r["label"], r["connection_type"], "AI Agent token exchange (private_key_jwt) on behalf of the logged-in user — real chain of custody (agent + user identity, both in the token)"))
    else:
        # No logged-in user (CLI mode) -- STS requires a real subject_token,
        # so fall back to the agent's own app-only credentials.
        token = get_client_credentials_token(os.environ[r["auth_server_id_env"]], r["scope"])
        receipts.append((r["label"], r["connection_type"], "OAuth access token (client_credentials fallback, no logged-in user) — app-only, no user context"))
    return MCPClient(r["base_url"], auth_header=("Authorization", f"Bearer {token}"))


def finance_client(receipts: list) -> MCPClient:
    r = RESOURCES["finance"]
    token = get_client_credentials_token(os.environ[r["auth_server_id_env"]], r["scope"])
    receipts.append((r["label"], r["connection_type"], "OAuth access token (client_credentials via Okta custom auth server) — app-only, no user context"))
    return MCPClient(r["base_url"], auth_header=("Authorization", f"Bearer {token}"))


def ticketing_client(receipts: list, subject_id_token: str | None) -> MCPClient | None:
    r = RESOURCES["ticketing"]
    if not subject_id_token:
        # This resource's authorization server only allows authorization_code
        # (real user context) -- no app-only fallback exists, unlike HR.
        receipts.append((r["label"], r["connection_type"], "SKIPPED — requires an authenticated end-user"))
        return None
    try:
        token = get_sts_token_for_user(subject_id_token, r["resource_indicator"])
    except ConsentRequired as e:
        e.resource_label, e.connection_type = r["label"], r["connection_type"]
        raise
    receipts.append((r["label"], r["connection_type"], "AI Agent token exchange (private_key_jwt) on behalf of the logged-in user — real chain of custody (agent + user identity, both in the token)"))
    return MCPClient(r["base_url"], auth_header=("Authorization", f"Bearer {token}"))


def analytics_client(receipts: list) -> MCPClient:
    r = RESOURCES["analytics"]
    key = get_vaulted_secret(r["env_fallback"], r["opa_key"])
    receipts.append((r["label"], r["connection_type"], "X-API-Key fetched just-in-time from vault"))
    return MCPClient(r["base_url"], auth_header=("X-API-Key", key))


def kudos_client(receipts: list, agent0_id_token: str | None) -> MCPClient | None:
    r = RESOURCES["kudos"]
    if not agent0_id_token:
        # Real XAA needs a subject_token whose `aud` is Agent0 specifically
        # (anti-confused-deputy check) -- the main app login's id_token
        # won't do, hence a separate token param from the other clients.
        receipts.append((r["label"], r["connection_type"], "SKIPPED — requires a separate Agent0-issued id_token"))
        return None
    issuer_url = os.environ[r["resource_issuer_url_env"]]
    token = get_xaa_token_for_user(issuer_url, r["scope"], agent0_id_token)
    receipts.append((r["label"], r["connection_type"], "Real Cross-App Access: ID-JAG minted by Okta's org authorization server, redeemed via jwt-bearer at the resource's own self-hosted authorization server — admin-defined access, no per-user consent prompt"))
    return MCPClient(r["base_url"], auth_header=("Authorization", f"Bearer {token}"))


ALL_RESOURCE_KEYS = {"hr", "ticketing", "finance", "analytics", "kudos"}
# Kudos Wall (real XAA) needs its Okta-side scope declaration finished --
# paused for now, so it's not on by default even though the code path
# works end-to-end up to that point. See SETUP.md §12.
DEFAULT_RESOURCE_KEYS = {"hr", "ticketing", "finance", "analytics"}


def gather_briefing_data(
    subject_id_token: str | None = None,
    agent0_id_token: str | None = None,
    selected: set[str] | None = None,
) -> tuple[dict, list]:
    if selected is None:
        selected = DEFAULT_RESOURCE_KEYS

    receipts = []
    hr = hr_client(receipts, subject_id_token) if "hr" in selected else None
    ticketing = ticketing_client(receipts, subject_id_token) if "ticketing" in selected else None
    finance = finance_client(receipts) if "finance" in selected else None
    analytics = analytics_client(receipts) if "analytics" in selected else None
    kudos = kudos_client(receipts, agent0_id_token) if "kudos" in selected else None

    data = {}
    if hr:
        data["org"] = hr.call_tool("list_employees")
        data["time_off"] = hr.call_tool("get_time_off_requests")
    if finance:
        data["budgets"] = finance.call_tool("list_all_budgets")
    if analytics:
        data["alerts"] = analytics.call_tool("get_alert_history", {"limit": 10})
        data["dashboards"] = analytics.call_tool("list_dashboards")
    if ticketing:
        data["open_tickets"] = ticketing.call_tool("list_tickets", {"status": "In Progress"})
        data["backlog_tickets"] = ticketing.call_tool("list_tickets", {"status": "Backlog"})
    if kudos:
        data["team_shoutouts"] = kudos.call_tool("list_kudos")
    return data, receipts


def print_receipts(receipts: list):
    print("\n--- O4AA Resource Connection Receipts ---")
    for label, connection_type, mechanism in receipts:
        print(f"  {label}\n    connection type : {connection_type}\n    secured via     : {mechanism}\n")


LANGUAGE_NAMES = {"en": "English", "es": "Latin American Spanish", "pt-BR": "Brazilian Portuguese"}


def narrate(data: dict, lang: str = "en") -> str:
    client = Anthropic()
    language_line = f" Write the entire briefing in {LANGUAGE_NAMES.get(lang, 'English')}."
    message = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=800,
        messages=[{
            "role": "user",
            "content": (
                "Write a concise Monday morning team-lead briefing from whichever of this "
                "raw data is present (org/time-off, budgets, tickets, system alerts, team "
                "shoutouts -- only cover what's actually in the data below). Use short "
                "sections with headers, call out anything that needs attention today, and "
                "if shoutouts are present end on those as a nice morale note."
                f"{language_line}\n\n"
                f"{data}"
            ),
        }],
    )
    return "".join(block.text for block in message.content if block.type == "text")


if __name__ == "__main__":
    data, receipts = gather_briefing_data()
    print_receipts(receipts)
    print("\n--- Monday Briefing ---\n")
    print(narrate(data))
