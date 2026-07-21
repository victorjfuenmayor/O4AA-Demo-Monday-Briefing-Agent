"""Monday Briefing Agent.

Assembles an internal ops briefing (org chart, budget status, open tickets,
system health) from four backend systems, each reached through a different
O4AA-governed resource connection, then asks Claude to narrate the result.

Usage: python main.py
"""

import os
from dotenv import load_dotenv
from anthropic import Anthropic

from mcp_client import MCPClient
from okta_auth import get_client_credentials_token, get_vaulted_secret
from resources import RESOURCES

load_dotenv()


def hr_client(receipts: list) -> MCPClient:
    r = RESOURCES["hr"]
    token = get_client_credentials_token(os.environ[r["auth_server_id_env"]], r["scope"])
    receipts.append((r["label"], r["connection_type"], "OAuth access token (client_credentials via Okta custom auth server) — app-only, no user context"))
    return MCPClient(r["base_url"], auth_header=("Authorization", f"Bearer {token}"))


def finance_client(receipts: list) -> MCPClient:
    r = RESOURCES["finance"]
    token = get_client_credentials_token(os.environ[r["auth_server_id_env"]], r["scope"])
    receipts.append((r["label"], r["connection_type"], "OAuth access token (client_credentials via Okta custom auth server) — app-only, no user context"))
    return MCPClient(r["base_url"], auth_header=("Authorization", f"Bearer {token}"))


def ticketing_client(receipts: list) -> MCPClient:
    r = RESOURCES["ticketing"]
    key = get_vaulted_secret(r["env_fallback"], r["opa_key"])
    receipts.append((r["label"], r["connection_type"], "X-API-Key fetched just-in-time from vault"))
    return MCPClient(r["base_url"], auth_header=("X-API-Key", key))


def analytics_client(receipts: list) -> MCPClient:
    r = RESOURCES["analytics"]
    key = get_vaulted_secret(r["env_fallback"], r["opa_key"])
    receipts.append((r["label"], r["connection_type"], "X-API-Key fetched just-in-time from vault"))
    return MCPClient(r["base_url"], auth_header=("X-API-Key", key))


def gather_briefing_data() -> tuple[dict, list]:
    receipts = []
    hr = hr_client(receipts)
    finance = finance_client(receipts)
    ticketing = ticketing_client(receipts)
    analytics = analytics_client(receipts)

    data = {
        "org": hr.call_tool("list_employees"),
        "time_off": hr.call_tool("get_time_off_requests"),
        "budgets": finance.call_tool("list_all_budgets"),
        "open_tickets": ticketing.call_tool("list_tickets", {"status": "In Progress"}),
        "backlog_tickets": ticketing.call_tool("list_tickets", {"status": "Backlog"}),
        "alerts": analytics.call_tool("get_alert_history", {"limit": 10}),
        "dashboards": analytics.call_tool("list_dashboards"),
    }
    return data, receipts


def print_receipts(receipts: list):
    print("\n--- O4AA Resource Connection Receipts ---")
    for label, connection_type, mechanism in receipts:
        print(f"  {label}\n    connection type : {connection_type}\n    secured via     : {mechanism}\n")


def narrate(data: dict) -> str:
    client = Anthropic()
    message = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=800,
        messages=[{
            "role": "user",
            "content": (
                "Write a concise Monday morning team-lead briefing from this raw data "
                "(org/time-off, budgets, tickets, system alerts). Use short sections "
                "with headers, call out anything that needs attention today.\n\n"
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
