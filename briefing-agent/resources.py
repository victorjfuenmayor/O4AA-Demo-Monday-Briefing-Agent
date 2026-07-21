"""Registry of the four backend resources this agent talks to, and which
O4AA mechanism secures each one. Ports match mcp-servers/*/README.md."""

RESOURCES = {
    "hr": {
        "label": "HR System (Workday-like)",
        "base_url": "http://localhost:8001",
        "connection_type": "Authorization server (native XAA)",
        "auth_server_id_env": "HR_AUTH_SERVER_ID",
        "scope": "hr.read",
    },
    "finance": {
        "label": "Finance System (SAP-like)",
        "base_url": "http://localhost:8002",
        "connection_type": "Authorization server (native XAA)",
        "auth_server_id_env": "FINANCE_AUTH_SERVER_ID",
        "scope": "finance.read",
    },
    "ticketing": {
        "label": "Ticketing System (Jira-like)",
        "base_url": "http://localhost:8004",
        "connection_type": "Vaulted secret (OPA / static key)",
        "env_fallback": "TICKETING_API_KEY",
        "opa_key": "ticketing-system-demo-key",
    },
    "analytics": {
        "label": "Analytics System (DataDog-like)",
        "base_url": "http://localhost:8003",
        "connection_type": "Vaulted secret (OPA / static key)",
        "env_fallback": "ANALYTICS_API_KEY",
        "opa_key": "analytics-system-demo-key",
    },
}
