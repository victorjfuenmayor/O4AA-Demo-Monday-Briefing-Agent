"""Registry of the backend resources this agent talks to, and which
O4AA mechanism secures each one. Ports match mcp-servers/*/README.md."""

RESOURCES = {
    "hr": {
        "label": "HR System (Workday-like)",
        "base_url": "http://localhost:8001",
        "connection_type": "AI Agent token exchange (OAuth STS)",
        "resource_indicator": "orn:okta:idp:00o4ecfvkTmcKID2Y696:client-auth-settings:rsc15gywhjsUkXj2m698",
        "auth_server_id_env": "HR_AUTH_SERVER_ID",  # still used by hr-system-mcp's own .env for token validation
        "scope": "hr.read",
    },
    "ticketing": {
        "label": "Ticketing System (Jira-like)",
        "base_url": "http://localhost:8004",
        "connection_type": "AI Agent token exchange via MCP Server (OAuth STS)",
        "resource_indicator": "orn:okta:idp:00o4ecfvkTmcKID2Y696:client-auth-settings:rsc15h0ryfgYPG4tq698",
        "scope": "ticketing.read",
    },
    "finance": {
        "label": "Finance System (SAP-like)",
        "base_url": "http://localhost:8002",
        "connection_type": "Authorization server (OAuth client_credentials)",
        "auth_server_id_env": "FINANCE_AUTH_SERVER_ID",
        "scope": "finance.read",
    },
    "analytics": {
        "label": "Analytics System (DataDog-like)",
        "base_url": "http://localhost:8003",
        "connection_type": "Vaulted secret (OPA / static key)",
        "env_fallback": "ANALYTICS_API_KEY",
        "opa_key": "analytics-system-demo-key",
    },
    "kudos": {
        "label": "Kudos Wall (Bonusly-like)",
        "base_url": "http://localhost:8005",
        "connection_type": "Cross-App Access (XAA) — ID-JAG",
        "resource_issuer_url_env": "KUDOS_WALL_ISSUER_URL",
        "scope": "kudos.read",
    },
}
