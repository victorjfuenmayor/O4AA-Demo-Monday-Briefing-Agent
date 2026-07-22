"""Translations for the Monday Briefing Agent UI.

Technical/protocol terms (OAuth, client_credentials, private_key_jwt,
JWKS, ID-JAG, MCP, XAA, STS, Resource Server, etc.) are deliberately left
untranslated in all three languages -- these are protocol/product names a
technical audience expects to see as-is, not localized.

TEXT holds general UI strings, keyed by a short name.
RESOURCE_TEXT holds per-resource content (label, connection type,
mechanism, when-to-use, pattern diagram name), keyed by resource key then
field then language.
"""

import streamlit as st

LANGUAGES = {
    "English (US)": "en",
    "Español (Latinoamérica)": "es",
    "Português (Brasil)": "pt-BR",
}

LANGUAGE_NAMES = {
    "en": "English",
    "es": "Latin American Spanish",
    "pt-BR": "Brazilian Portuguese",
}


def current_lang() -> str:
    return st.session_state.get("lang", "en")


# Module-level cache, same pattern as auth.save_user/get_saved_user --
# st.session_state doesn't survive a hard browser refresh (a fresh
# session gets fresh state), but this process-level global does, since
# it's the same running Streamlit server across that refresh.
_saved_language: str | None = None


def save_language(code: str) -> None:
    global _saved_language
    _saved_language = code


def get_saved_language() -> str | None:
    return _saved_language


def t(key: str) -> str:
    return TEXT[key][current_lang()]


def rt(resource_key: str, field: str) -> str:
    return RESOURCE_TEXT[resource_key][field][current_lang()]


TEXT = {
    "sign_in_prompt": {
        "en": "Sign in with your Okta account to continue.",
        "es": "Inicia sesión con tu cuenta de Okta para continuar.",
        "pt-BR": "Faça login com sua conta Okta para continuar.",
    },
    "login_button": {
        "en": "Log in with Okta",
        "es": "Iniciar sesión con Okta",
        "pt-BR": "Fazer login com Okta",
    },
    "login_error_state_mismatch": {
        "en": "Login failed: state mismatch. Try logging in again.",
        "es": "Error de inicio de sesión: el parámetro state no coincide. Intenta iniciar sesión de nuevo.",
        "pt-BR": "Falha no login: incompatibilidade de state. Tente fazer login novamente.",
    },
    "signed_in_as": {
        "en": "Signed in as **{name}**",
        "es": "Sesión iniciada como **{name}**",
        "pt-BR": "Conectado como **{name}**",
    },
    "logout_button": {
        "en": "Log out",
        "es": "Cerrar sesión",
        "pt-BR": "Sair",
    },
    "language_label": {
        "en": "Language",
        "es": "Idioma",
        "pt-BR": "Idioma",
    },
    "caption_secured": {
        "en": "Every connection below is secured end-to-end by Okta for AI Agents (O4AA).",
        "es": "Cada conexión a continuación está protegida de extremo a extremo por Okta for AI Agents (O4AA).",
        "pt-BR": "Cada conexão abaixo é protegida de ponta a ponta pelo Okta for AI Agents (O4AA).",
    },
    "architecture_expander": {
        "en": "🗺️ Full architecture diagram",
        "es": "🗺️ Diagrama de arquitectura completo",
        "pt-BR": "🗺️ Diagrama de arquitetura completo",
    },
    "architecture_missing": {
        "en": "(architecture.png not yet exported to briefing-agent/assets/)",
        "es": "(architecture.png aún no se exportó a briefing-agent/assets/)",
        "pt-BR": "(architecture.png ainda não foi exportado para briefing-agent/assets/)",
    },
    "mcp_vs_resource_popover": {
        "en": "❓ MCP Server vs Resource Server — what's the difference?",
        "es": "❓ MCP Server vs Resource Server: ¿cuál es la diferencia?",
        "pt-BR": "❓ MCP Server vs Resource Server: qual é a diferença?",
    },
    "mcp_vs_resource_body": {
        "en": """
**Resource Server** (used by HR):
- Protocol-agnostic — Okta doesn't assume anything about the backend.
- You manually tell Okta everything: the resource URL, and which existing
  authorization server's Authorize/Token endpoints protect it.
- No live reachability check — Okta just stores the URL as metadata,
  never calls it.

**MCP Server** (used by Ticketing):
- Assumes the backend speaks the Model Context Protocol (`tools/list`,
  `tools/call`) — exactly what these sample servers are.
- Okta **auto-discovers** the protecting authorization server by calling a
  standard discovery endpoint (`/.well-known/oauth-protected-resource`)
  that the MCP server itself exposes — no manual endpoint entry.
- Because of that live discovery call, Okta must be able to **reach the
  server from its own cloud** — a public tunnel (we used `ngrok`) is
  required for a locally-running server. Editing an existing entry doesn't
  retrigger discovery; delete and recreate it if the endpoint changes.

**What's identical underneath:** once registered, both use the exact same
runtime mechanism (`get_sts_token_for_user()` in `okta_auth.py`) — the
distinction is entirely in *how the resource gets registered and
discovered*, not in how the resulting token or chain-of-custody works.
See `SETUP.md` §9 for the full step-by-step for both.
        """,
        "es": """
**Resource Server** (usado por HR):
- Agnóstico al protocolo — Okta no asume nada sobre el backend.
- Le indicas todo manualmente a Okta: la URL del recurso y qué servidor de
  autorización existente protege sus endpoints de Authorize/Token.
- Sin verificación de accesibilidad en vivo — Okta solo guarda la URL como
  metadato, nunca la llama.

**MCP Server** (usado por Ticketing):
- Asume que el backend habla el Model Context Protocol (`tools/list`,
  `tools/call`) — exactamente lo que son estos servidores de ejemplo.
- Okta **descubre automáticamente** el servidor de autorización que lo
  protege, llamando a un endpoint de descubrimiento estándar
  (`/.well-known/oauth-protected-resource`) que el propio servidor MCP
  expone — sin ingresar el endpoint manualmente.
- Debido a esa llamada de descubrimiento en vivo, Okta debe poder
  **alcanzar el servidor desde su propia nube** — se requiere un túnel
  público (usamos `ngrok`) para un servidor que corre localmente. Editar
  una entrada existente no vuelve a disparar el descubrimiento; hay que
  eliminarla y volver a crearla si el endpoint cambia.

**Lo que es idéntico por debajo:** una vez registrados, ambos usan
exactamente el mismo mecanismo en tiempo de ejecución
(`get_sts_token_for_user()` en `okta_auth.py`) — la distinción está
completamente en *cómo se registra y descubre el recurso*, no en cómo
funciona el token resultante ni la cadena de custodia.
Consulta `SETUP.md` §9 para el paso a paso completo de ambos.
        """,
        "pt-BR": """
**Resource Server** (usado pelo HR):
- Agnóstico ao protocolo — o Okta não assume nada sobre o backend.
- Você informa tudo manualmente ao Okta: a URL do recurso e qual servidor
  de autorização existente protege seus endpoints de Authorize/Token.
- Sem verificação de disponibilidade em tempo real — o Okta apenas
  armazena a URL como metadado, nunca a chama.

**MCP Server** (usado pelo Ticketing):
- Assume que o backend fala o Model Context Protocol (`tools/list`,
  `tools/call`) — exatamente o que esses servidores de exemplo são.
- O Okta **descobre automaticamente** o servidor de autorização que o
  protege, chamando um endpoint de descoberta padrão
  (`/.well-known/oauth-protected-resource`) que o próprio servidor MCP
  expõe — sem digitar o endpoint manualmente.
- Por causa dessa chamada de descoberta em tempo real, o Okta precisa
  conseguir **alcançar o servidor a partir da própria nuvem** — é
  necessário um túnel público (usamos o `ngrok`) para um servidor rodando
  localmente. Editar uma entrada existente não dispara a descoberta de
  novo; é preciso excluir e recriar a entrada se o endpoint mudar.

**O que é idêntico por baixo dos panos:** uma vez registrados, ambos usam
exatamente o mesmo mecanismo em tempo de execução
(`get_sts_token_for_user()` em `okta_auth.py`) — a distinção está
inteiramente em *como o recurso é registrado e descoberto*, não em como o
token resultante ou a cadeia de custódia funcionam.
Veja `SETUP.md` §9 para o passo a passo completo de ambos.
        """,
    },
    "systems_subheader": {
        "en": "Which systems should the agent connect to?",
        "es": "¿A qué sistemas debería conectarse el agente?",
        "pt-BR": "A quais sistemas o agente deve se conectar?",
    },
    "include_checkbox": {
        "en": "Include in briefing",
        "es": "Incluir en el resumen",
        "pt-BR": "Incluir no resumo",
    },
    "paused_suffix": {
        "en": " (paused)",
        "es": " (en pausa)",
        "pt-BR": " (pausado)",
    },
    "details_popover": {
        "en": "Details",
        "es": "Detalles",
        "pt-BR": "Detalhes",
    },
    "expand_diagram": {
        "en": "🔍 Expand diagram",
        "es": "🔍 Ampliar diagrama",
        "pt-BR": "🔍 Expandir diagrama",
    },
    "shrink_diagram": {
        "en": "Shrink diagram",
        "es": "Reducir diagrama",
        "pt-BR": "Reduzir diagrama",
    },
    "generate_button": {
        "en": "Generate this week's briefing",
        "es": "Generar el resumen de esta semana",
        "pt-BR": "Gerar o resumo desta semana",
    },
    "kudos_login_warning": {
        "en": (
            "Kudos Wall (real Cross-App Access) needs a separate one-time login through "
            "the XAA Requester app — its id_token has to be issued *by that app specifically* "
            "(an anti-confused-deputy check XAA enforces), not the one you're already logged "
            "in with."
        ),
        "es": (
            "Kudos Wall (Cross-App Access real) necesita un inicio de sesión adicional, único, "
            "a través de la app XAA Requester — su id_token debe ser emitido *específicamente "
            "por esa app* (una verificación anti-confused-deputy que exige XAA), no por la que "
            "ya usaste para iniciar sesión."
        ),
        "pt-BR": (
            "O Kudos Wall (Cross-App Access real) precisa de um login adicional, único, pelo "
            "app XAA Requester — o id_token precisa ser emitido *especificamente por esse app* "
            "(uma verificação anti-confused-deputy exigida pelo XAA), não pelo app com o qual "
            "você já está logado."
        ),
    },
    "kudos_login_button": {
        "en": "Log in for Kudos Wall",
        "es": "Iniciar sesión para Kudos Wall",
        "pt-BR": "Fazer login para o Kudos Wall",
    },
    "kudos_login_caption": {
        "en": 'Click "Generate this week\'s briefing" again afterward.',
        "es": 'Después, haz clic de nuevo en "Generar el resumen de esta semana".',
        "pt-BR": 'Depois, clique novamente em "Gerar o resumo desta semana".',
    },
    "select_at_least_one": {
        "en": "Select at least one system above.",
        "es": "Selecciona al menos un sistema arriba.",
        "pt-BR": "Selecione ao menos um sistema acima.",
    },
    "connecting_spinner": {
        "en": "Connecting to {systems} systems...",
        "es": "Conectando con los sistemas: {systems}...",
        "pt-BR": "Conectando aos sistemas: {systems}...",
    },
    "consent_warning": {
        "en": "One-time consent needed for **{resource}** before the agent can act on your behalf here.",
        "es": "Se necesita un consentimiento único para **{resource}** antes de que el agente pueda actuar en tu nombre aquí.",
        "pt-BR": "É necessário um consentimento único para **{resource}** antes que o agente possa agir em seu nome aqui.",
    },
    "consent_explanation_sts_resource": {
        "en": (
            "**Why this one asks:** this connection uses Okta's native AI Agent token "
            "exchange (registered as a *Resource Server*) — the access token Okta hands "
            "back doesn't just say \"the agent is calling,\" it also asserts *your* real "
            "identity (`sub`/`uid`) alongside the agent's (`cid`). Because the token makes "
            "a claim about you specifically, Okta requires you to approve that assertion "
            "once, per resource. After this, it's silent — no repeat prompts."
        ),
        "es": (
            "**Por qué pregunta esto:** esta conexión usa el intercambio de tokens nativo de "
            "AI Agent de Okta (registrado como *Resource Server*) — el token de acceso que "
            "devuelve Okta no solo dice \"el agente está llamando\", también afirma *tu* "
            "identidad real (`sub`/`uid`) junto con la del agente (`cid`). Como el token hace "
            "una afirmación específicamente sobre ti, Okta te exige aprobar esa afirmación una "
            "vez, por recurso. Después de esto, queda en silencio — sin avisos repetidos."
        ),
        "pt-BR": (
            "**Por que isso pergunta:** esta conexão usa a troca de tokens nativa de AI Agent "
            "do Okta (registrada como *Resource Server*) — o token de acesso que o Okta "
            "devolve não diz apenas \"o agente está chamando\", ele também afirma *sua* "
            "identidade real (`sub`/`uid`) junto com a do agente (`cid`). Como o token faz uma "
            "afirmação especificamente sobre você, o Okta exige que você aprove essa afirmação "
            "uma vez, por recurso. Depois disso, fica em silêncio — sem avisos repetidos."
        ),
    },
    "consent_explanation_sts_mcp": {
        "en": (
            "**Why this one asks:** same AI Agent token exchange mechanism as HR — the "
            "token asserts your real identity alongside the agent's — just registered as "
            "an *MCP Server* instead of a Resource Server (Okta auto-discovered its "
            "authorization server rather than it being typed in by hand). Because the "
            "token still asserts *you* specifically, it needs the same one-time consent, "
            "granted separately from HR's."
        ),
        "es": (
            "**Por qué pregunta esto:** el mismo mecanismo de intercambio de tokens de AI "
            "Agent que HR — el token afirma tu identidad real junto con la del agente — solo "
            "que está registrado como *MCP Server* en lugar de Resource Server (Okta "
            "descubrió automáticamente su servidor de autorización en lugar de que se "
            "escribiera a mano). Como el token sigue afirmando específicamente que eres tú, "
            "necesita el mismo consentimiento único, otorgado por separado del de HR."
        ),
        "pt-BR": (
            "**Por que isso pergunta:** o mesmo mecanismo de troca de tokens de AI Agent do "
            "HR — o token afirma sua identidade real junto com a do agente — só que "
            "registrado como *MCP Server* em vez de Resource Server (o Okta descobriu "
            "automaticamente seu servidor de autorização em vez de ser digitado manualmente). "
            "Como o token ainda afirma especificamente que é você, ele precisa do mesmo "
            "consentimento único, concedido separadamente do consentimento do HR."
        ),
    },
    "consent_explanation_default": {
        "en": "This resource asserts your identity in the token it returns, so Okta requires one-time approval before the agent can use it on your behalf.",
        "es": "Este recurso afirma tu identidad en el token que devuelve, por lo que Okta exige una aprobación única antes de que el agente pueda usarlo en tu nombre.",
        "pt-BR": "Este recurso afirma sua identidade no token que retorna, portanto o Okta exige uma aprovação única antes que o agente possa usá-lo em seu nome.",
    },
    "consent_contrast_caption": {
        "en": (
            "Contrast: Finance (`client_credentials`) and Analytics (OPA vault) never show this "
            "prompt — those tokens are app-only and never claim to represent a specific person. "
            "Kudos Wall (real Cross-App Access) also never prompts, for a different reason: it "
            "*does* carry your identity, but XAA replaces per-user consent with admin-defined "
            "access — appropriate here since kudos data isn't personally sensitive the way HR "
            "data is."
        ),
        "es": (
            "Contraste: Finance (`client_credentials`) y Analytics (bóveda de OPA) nunca "
            "muestran este aviso — esos tokens son solo de la aplicación y nunca afirman "
            "representar a una persona específica. Kudos Wall (Cross-App Access real) tampoco "
            "lo pide, pero por una razón distinta: *sí* transporta tu identidad, pero XAA "
            "reemplaza el consentimiento por usuario con acceso definido por el administrador "
            "— algo apropiado aquí porque los datos de kudos no son tan sensibles como los de "
            "HR."
        ),
        "pt-BR": (
            "Contraste: Finance (`client_credentials`) e Analytics (cofre da OPA) nunca "
            "mostram esse aviso — esses tokens são apenas do aplicativo e nunca afirmam "
            "representar uma pessoa específica. O Kudos Wall (Cross-App Access real) também "
            "nunca pede, mas por um motivo diferente: ele *carrega* sua identidade, mas o XAA "
            "substitui o consentimento por usuário por acesso definido pelo administrador — "
            "apropriado aqui, já que os dados de kudos não são tão sensíveis quanto os dados "
            "de HR."
        ),
    },
    "consent_info_new_tab": {
        "en": (
            "The link below opens Okta's consent screen in a **new tab** on purpose — it redirects "
            "to an Okta-owned page, not back into this app, so opening it here would log you out of "
            "this session. Approve access there, **close that tab**, then come back to **this tab** "
            "and click \"Generate this week's briefing\" again."
        ),
        "es": (
            "El enlace de abajo abre la pantalla de consentimiento de Okta en una **pestaña "
            "nueva** a propósito — redirige a una página propiedad de Okta, no de vuelta a esta "
            "app, así que abrirlo aquí cerraría tu sesión. Aprueba el acceso ahí, **cierra esa "
            "pestaña**, y luego vuelve a **esta pestaña** y haz clic de nuevo en \"Generar el "
            "resumen de esta semana\"."
        ),
        "pt-BR": (
            "O link abaixo abre a tela de consentimento do Okta em uma **nova aba** de "
            "propósito — ele redireciona para uma página do próprio Okta, não de volta para "
            "este app, então abri-lo aqui encerraria sua sessão. Aprove o acesso lá, **feche "
            "essa aba**, depois volte para **esta aba** e clique novamente em \"Gerar o resumo "
            "desta semana\"."
        ),
    },
    "grant_access_link": {
        "en": "Grant access",
        "es": "Otorgar acceso",
        "pt-BR": "Conceder acesso",
    },
    "narrating_spinner": {
        "en": "Narrating...",
        "es": "Narrando...",
        "pt-BR": "Narrando...",
    },
    "briefing_subheader": {
        "en": "This Week's Briefing",
        "es": "El resumen de esta semana",
        "pt-BR": "O resumo desta semana",
    },
    "raw_data_expander": {
        "en": "Raw data pulled from each system",
        "es": "Datos sin procesar obtenidos de cada sistema",
        "pt-BR": "Dados brutos obtidos de cada sistema",
    },
    "click_button_info": {
        "en": "Click the button to run the agent live against ligalac.okta.com.",
        "es": "Haz clic en el botón para ejecutar el agente en vivo contra ligalac.okta.com.",
        "pt-BR": "Clique no botão para executar o agente em tempo real contra ligalac.okta.com.",
    },
    "sidebar_trace_subheader": {
        "en": "🔍 Live Okta ↔ MCP trace",
        "es": "🔍 Traza en vivo Okta ↔ MCP",
        "pt-BR": "🔍 Rastreamento em tempo real Okta ↔ MCP",
    },
    "sidebar_trace_caption": {
        "en": (
            "Every HTTP call this agent made for the last briefing, in order. "
            "Secrets are redacted; tokens are truncated with their claims decoded "
            "alongside (unverified — for display only)."
        ),
        "es": (
            "Cada llamada HTTP que hizo este agente para el último resumen, en orden. "
            "Los secretos están ocultos; los tokens se truncan mostrando además sus claims "
            "decodificados (sin verificar — solo para visualización)."
        ),
        "pt-BR": (
            "Cada chamada HTTP feita por este agente para o último resumo, em ordem. Os "
            "segredos são ocultados; os tokens são truncados, exibindo também suas claims "
            "decodificadas (não verificadas — apenas para exibição)."
        ),
    },
    "clear_trace_button": {
        "en": "Clear trace",
        "es": "Borrar traza",
        "pt-BR": "Limpar rastro",
    },
    "sidebar_trace_empty": {
        "en": "Generate a briefing to populate this.",
        "es": "Genera un resumen para completar esto.",
        "pt-BR": "Gere um resumo para preencher isto.",
    },
    "trace_request_label": {
        "en": "**Request (redacted)**",
        "es": "**Solicitud (con datos ocultos)**",
        "pt-BR": "**Solicitação (com dados ocultados)**",
    },
    "trace_headers_label": {
        "en": "**Headers**",
        "es": "**Encabezados**",
        "pt-BR": "**Cabeçalhos**",
    },
    "trace_response_label": {
        "en": "**Response — {status}**",
        "es": "**Respuesta — {status}**",
        "pt-BR": "**Resposta — {status}**",
    },
}

RESOURCE_TEXT = {
    "hr": {
        "label": {"en": "HR System", "es": "Sistema de RR. HH.", "pt-BR": "Sistema de RH"},
        "connection_type": {
            "en": "AI Agent token exchange (OAuth STS)",
            "es": "Intercambio de tokens de AI Agent (OAuth STS)",
            "pt-BR": "Troca de tokens de AI Agent (OAuth STS)",
        },
        "mechanism": {
            "en": "AI Agent token exchange (private_key_jwt) on behalf of the logged-in user — real chain of custody (agent + user identity, both in the token)",
            "es": "Intercambio de tokens de AI Agent (private_key_jwt) en nombre del usuario que inició sesión — cadena de custodia real (identidad del agente y del usuario, ambas en el token)",
            "pt-BR": "Troca de tokens de AI Agent (private_key_jwt) em nome do usuário conectado — cadeia de custódia real (identidade do agente e do usuário, ambas no token)",
        },
        "when_to_use": {
            "en": (
                "**Why:** the resource needs to know *which specific person* is asking, not just "
                "that some agent is asking — e.g. data scoped per-employee, actions attributable to a "
                "real human for audit purposes.\n\n"
                "**Requires:** the backend (or a layer in front of it) speaks OAuth2 and can be "
                "registered as an Okta Resource Server (its authorize/token endpoints, hand-entered); "
                "a real logged-in user available to grant one-time consent."
            ),
            "es": (
                "**Por qué:** el recurso necesita saber *qué persona específica* está preguntando, "
                "no solo que algún agente está preguntando — por ejemplo, datos delimitados por "
                "empleado, acciones atribuibles a una persona real con fines de auditoría.\n\n"
                "**Requiere:** que el backend (o una capa frente a él) hable OAuth2 y pueda "
                "registrarse como Resource Server de Okta (sus endpoints de authorize/token, "
                "ingresados a mano); un usuario real con sesión iniciada disponible para otorgar "
                "el consentimiento único."
            ),
            "pt-BR": (
                "**Por quê:** o recurso precisa saber *qual pessoa específica* está solicitando, "
                "não apenas que algum agente está solicitando — por exemplo, dados delimitados por "
                "funcionário, ações atribuíveis a uma pessoa real para fins de auditoria.\n\n"
                "**Requer:** que o backend (ou uma camada na frente dele) fale OAuth2 e possa ser "
                "registrado como Resource Server do Okta (seus endpoints de authorize/token, "
                "digitados manualmente); um usuário real conectado disponível para conceder o "
                "consentimento único."
            ),
        },
        "pattern_name": {
            "en": "Pattern 2 — internal agent, user-delegated (workforce)",
            "es": "Patrón 2 — agente interno, delegado por usuario (fuerza laboral)",
            "pt-BR": "Padrão 2 — agente interno, delegado pelo usuário (força de trabalho)",
        },
    },
    "ticketing": {
        "label": {"en": "Ticketing System", "es": "Sistema de Tickets", "pt-BR": "Sistema de Tickets"},
        "connection_type": {
            "en": "AI Agent token exchange via MCP Server (OAuth STS)",
            "es": "Intercambio de tokens de AI Agent vía MCP Server (OAuth STS)",
            "pt-BR": "Troca de tokens de AI Agent via MCP Server (OAuth STS)",
        },
        "mechanism": {
            "en": "AI Agent token exchange (private_key_jwt) on behalf of the logged-in user — real chain of custody (agent + user identity, both in the token)",
            "es": "Intercambio de tokens de AI Agent (private_key_jwt) en nombre del usuario que inició sesión — cadena de custodia real (identidad del agente y del usuario, ambas en el token)",
            "pt-BR": "Troca de tokens de AI Agent (private_key_jwt) em nome do usuário conectado — cadeia de custódia real (identidade do agente e do usuário, ambas no token)",
        },
        "when_to_use": {
            "en": (
                "**Why:** same need as HR — real per-user delegation — but the backend already speaks "
                "the Model Context Protocol, so registration can be automatic instead of hand-entered.\n\n"
                "**Requires:** the backend exposes MCP's `/.well-known/oauth-protected-resource` "
                "discovery endpoint; it must be live-reachable from Okta's cloud at registration time "
                "(a public tunnel for anything running locally); no app-only fallback is possible once "
                "the resource's policy is set to `authorization_code` only."
            ),
            "es": (
                "**Por qué:** la misma necesidad que HR — delegación real por usuario — pero el "
                "backend ya habla el Model Context Protocol, así que el registro puede ser "
                "automático en lugar de ingresado a mano.\n\n"
                "**Requiere:** que el backend expone el endpoint de descubrimiento de MCP "
                "`/.well-known/oauth-protected-resource`; debe ser alcanzable en vivo desde la nube "
                "de Okta en el momento del registro (un túnel público para cualquier cosa que corra "
                "localmente); no existe una alternativa solo de aplicación una vez que la política "
                "del recurso se configura únicamente en `authorization_code`."
            ),
            "pt-BR": (
                "**Por quê:** a mesma necessidade do HR — delegação real por usuário — mas o "
                "backend já fala o Model Context Protocol, então o registro pode ser automático em "
                "vez de digitado manualmente.\n\n"
                "**Requer:** que o backend exponha o endpoint de descoberta do MCP "
                "`/.well-known/oauth-protected-resource`; ele precisa estar acessível em tempo real "
                "a partir da nuvem do Okta no momento do registro (um túnel público para qualquer "
                "coisa rodando localmente); não há alternativa somente de aplicativo depois que a "
                "política do recurso é definida apenas como `authorization_code`."
            ),
        },
        "pattern_name": {
            "en": "Pattern 6 — MCP Server Registry + STS Brokered Consent",
            "es": "Patrón 6 — Registro de MCP Server + Consentimiento Intermediado por STS",
            "pt-BR": "Padrão 6 — Registro de MCP Server + Consentimento Intermediado por STS",
        },
    },
    "finance": {
        "label": {"en": "Finance System", "es": "Sistema de Finanzas", "pt-BR": "Sistema Financeiro"},
        "connection_type": {
            "en": "Authorization server (OAuth client_credentials)",
            "es": "Servidor de autorización (OAuth client_credentials)",
            "pt-BR": "Servidor de autorização (OAuth client_credentials)",
        },
        "mechanism": {
            "en": "OAuth access token (client_credentials via Okta custom auth server) — app-only, no user context",
            "es": "Token de acceso OAuth (client_credentials vía servidor de autorización personalizado de Okta) — solo de la aplicación, sin contexto de usuario",
            "pt-BR": "Token de acesso OAuth (client_credentials via servidor de autorização personalizado do Okta) — somente do aplicativo, sem contexto de usuário",
        },
        "when_to_use": {
            "en": (
                "**Why:** app-only automation where no individual human's identity matters — a "
                "scheduled job, a dashboard pulling aggregate numbers nobody's access needs to be "
                "scoped per-person.\n\n"
                "**Requires:** just an OAuth2-capable backend and a custom Okta authorization server — "
                "no login flow, no consent screen, fastest to stand up. Trade-off: zero user-level "
                "chain of custody, so it's the wrong choice the moment the data *is* personally scoped."
            ),
            "es": (
                "**Por qué:** automatización solo de la aplicación donde no importa la identidad de "
                "ninguna persona en particular — un trabajo programado, un dashboard que trae números "
                "agregados cuyo acceso no necesita delimitarse por persona.\n\n"
                "**Requiere:** solo un backend compatible con OAuth2 y un servidor de autorización "
                "personalizado de Okta — sin flujo de inicio de sesión, sin pantalla de consentimiento, "
                "el más rápido de implementar. Compensación: cero cadena de custodia a nivel de "
                "usuario, así que es la opción equivocada en el momento en que los datos *sí* están "
                "delimitados por persona."
            ),
            "pt-BR": (
                "**Por quê:** automação somente do aplicativo, onde a identidade de nenhuma pessoa "
                "específica importa — um job agendado, um dashboard que traz números agregados cujo "
                "acesso não precisa ser delimitado por pessoa.\n\n"
                "**Requer:** apenas um backend compatível com OAuth2 e um servidor de autorização "
                "personalizado do Okta — sem fluxo de login, sem tela de consentimento, o mais rápido "
                "de configurar. Contrapartida: nenhuma cadeia de custódia em nível de usuário, então é "
                "a escolha errada no momento em que os dados *forem* delimitados por pessoa."
            ),
        },
        "pattern_name": {
            "en": "Pattern 4 — internal agent, fully autonomous, no user",
            "es": "Patrón 4 — agente interno, totalmente autónomo, sin usuario",
            "pt-BR": "Padrão 4 — agente interno, totalmente autônomo, sem usuário",
        },
    },
    "analytics": {
        "label": {"en": "Analytics System", "es": "Sistema de Analítica", "pt-BR": "Sistema de Analytics"},
        "connection_type": {
            "en": "Vaulted secret (OPA / static key)",
            "es": "Secreto en bóveda (OPA / clave estática)",
            "pt-BR": "Segredo em cofre (OPA / chave estática)",
        },
        "mechanism": {
            "en": "X-API-Key fetched just-in-time from vault",
            "es": "X-API-Key obtenida justo a tiempo desde la bóveda",
            "pt-BR": "X-API-Key obtida just-in-time a partir do cofre",
        },
        "when_to_use": {
            "en": (
                "**Why:** the backend predates OAuth entirely and only understands a static API "
                "key/header — there's no better protocol to reach for.\n\n"
                "**Requires:** nothing from the backend itself (it can't change); the win is entirely "
                "on the agent's side — the raw key is fetched just-in-time from a vault instead of "
                "sitting in config. Still weaker than real OAuth: whoever holds the revealed key can "
                "reuse it until it's rotated."
            ),
            "es": (
                "**Por qué:** el backend es anterior a OAuth por completo y solo entiende una "
                "clave/encabezado API estático — no hay un protocolo mejor al que recurrir.\n\n"
                "**Requiere:** nada del backend en sí (no puede cambiar); la ganancia está "
                "completamente del lado del agente — la clave en bruto se obtiene justo a tiempo "
                "desde una bóveda en lugar de quedarse en la configuración. Aun así es más débil "
                "que OAuth real: quien tenga la clave revelada puede reutilizarla hasta que se rote."
            ),
            "pt-BR": (
                "**Por quê:** o backend é anterior ao OAuth por completo e só entende uma "
                "chave/cabeçalho de API estático — não há um protocolo melhor para recorrer.\n\n"
                "**Requer:** nada do próprio backend (ele não pode mudar); o ganho está totalmente "
                "do lado do agente — a chave bruta é obtida just-in-time a partir de um cofre em "
                "vez de ficar na configuração. Ainda assim é mais fraco que OAuth real: quem tiver "
                "a chave revelada pode reutilizá-la até que seja rotacionada."
            ),
        },
        "pattern_name": {
            "en": "Credential Vault Broker (building block of Pattern 1)",
            "es": "Credential Vault Broker (bloque de construcción del Patrón 1)",
            "pt-BR": "Credential Vault Broker (bloco de construção do Padrão 1)",
        },
    },
    "kudos": {
        "label": {"en": "Kudos Wall", "es": "Muro de Kudos", "pt-BR": "Mural de Kudos"},
        "connection_type": {
            "en": "Cross-App Access (XAA) — ID-JAG",
            "es": "Cross-App Access (XAA) — ID-JAG",
            "pt-BR": "Cross-App Access (XAA) — ID-JAG",
        },
        "mechanism": {
            "en": "Real Cross-App Access: ID-JAG minted by Okta's org authorization server, redeemed via jwt-bearer at the resource's own self-hosted authorization server — admin-defined access, no per-user consent prompt",
            "es": "Cross-App Access real: el ID-JAG es emitido por el servidor de autorización de la organización en Okta y se redime vía jwt-bearer en el propio servidor de autorización autohospedado del recurso — acceso definido por el administrador, sin aviso de consentimiento por usuario",
            "pt-BR": "Cross-App Access real: o ID-JAG é emitido pelo servidor de autorização da organização no Okta e resgatado via jwt-bearer no próprio servidor de autorização auto-hospedado do recurso — acesso definido pelo administrador, sem aviso de consentimento por usuário",
        },
        "when_to_use": {
            "en": (
                "**Why:** the resource's own team wants to run and trust *their own* authorization "
                "server instead of relying on Okta's directly — common for a SaaS vendor who already "
                "has one — or the access is broad/low-sensitivity enough that admin-defined access "
                "(no per-user consent friction) is the right posture rather than a shortcut.\n\n"
                "**Requires:** the resource must be able to run its own authorization server capable of "
                "verifying an externally-issued assertion (the ID-JAG) and minting its own tokens — "
                "meaningfully more backend work than every other pattern here, since Okta is no longer "
                "the one validating the final access token."
            ),
            "es": (
                "**Por qué:** el propio equipo del recurso quiere operar y confiar en *su propio* "
                "servidor de autorización en lugar de depender directamente del de Okta — algo común "
                "en un proveedor SaaS que ya tiene uno — o el acceso es suficientemente amplio/de baja "
                "sensibilidad como para que el acceso definido por el administrador (sin la fricción "
                "de consentimiento por usuario) sea la postura correcta y no un atajo.\n\n"
                "**Requiere:** que el recurso pueda operar su propio servidor de autorización capaz de "
                "verificar una aserción emitida externamente (el ID-JAG) y de emitir sus propios "
                "tokens — considerablemente más trabajo de backend que cualquier otro patrón aquí, ya "
                "que Okta deja de ser quien valida el token de acceso final."
            ),
            "pt-BR": (
                "**Por quê:** a própria equipe do recurso quer operar e confiar no *seu próprio* "
                "servidor de autorização em vez de depender diretamente do Okta — comum em um "
                "fornecedor SaaS que já possui um — ou o acesso é amplo/de baixa sensibilidade o "
                "suficiente para que o acesso definido pelo administrador (sem a fricção do "
                "consentimento por usuário) seja a postura correta, e não um atalho.\n\n"
                "**Requer:** que o recurso consiga operar seu próprio servidor de autorização capaz "
                "de verificar uma asserção emitida externamente (o ID-JAG) e emitir seus próprios "
                "tokens — significativamente mais trabalho de backend do que qualquer outro padrão "
                "aqui, já que o Okta deixa de ser quem valida o token de acesso final."
            ),
        },
        "pattern_name": {
            "en": "Real Cross-App Access (ID-JAG) — resource runs its own authorization server",
            "es": "Cross-App Access real (ID-JAG) — el recurso opera su propio servidor de autorización",
            "pt-BR": "Cross-App Access real (ID-JAG) — o recurso opera seu próprio servidor de autorização",
        },
    },
}
