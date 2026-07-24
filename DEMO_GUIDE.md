# Demo Guide — pitching O4AA with the Monday Briefing Agent

For SEs driving the keyboard and AEs narrating. This demo proves a specific,
well-scoped claim: **one agent, five backend systems, five genuinely
different auth postures — including three where the token carries the real
end user's identity, not just the agent's, achieved three different ways —
one governed control plane.**
Don't oversell it as more than that — see "What this demo is NOT" below.
(Four of the five are live end-to-end today; the fifth, Kudos Wall's real
XAA connection, is fully built and wired but paused one Okta config step
short of working — see the anticipated-questions section for how to talk
about it honestly.)

## The one-sentence pitch

"Watch an AI agent pull real data from backend systems — some where the
token it gets proves *both* which agent is asking *and* which real person
it's acting for (achieved three different ways in Okta), one that speaks
plain OAuth with no user context at all, and one that only understands an
old static API key — and at no point does the agent's code contain a single
credential. Everything it can touch, and everything it's allowed to do, is
declared and governed in Okta."

## Before you start

- All four *working* MCP servers running (`SETUP.md` step 6), agent's
  `.env` filled in. Kudos Wall's server (`mcp-servers/kudos-wall-mcp/`,
  port 8005) can run too if you want to show the paused state, but it's
  unchecked by default in the UI so it's not required.
- Prefer the Streamlit UI (`streamlit run app.py`, `SETUP.md` §7) over the
  CLI for anything customer-facing — it's gated behind a real Okta login,
  which is itself worth narrating (see step 0 below), and looks far better
  on a shared screen than a terminal.
- A browser tab open on the AI Agent's page in Okta Universal Directory
  (Directory → the agent) showing its resource connections — you'll want to
  flip to this mid-demo.
- Run it once yourself first. Data (mock employee names, ticket IDs, alert
  states) is static/deterministic aside from timestamps, so the output is
  predictable — read it once so you're not surprised live.
- The landing page has a sidebar button ("🗺️ Full architecture diagram")
  that opens a full-resolution popup showing every component — Streamlit
  modules, Okta tenant objects, OPA, Anthropic, all 5 backend MCP servers.
  Good opener for a technical audience before diving into any one
  connection's detail. (Each resource's own pattern diagram, inside its
  Details popover, opens the same way via an "Expand diagram" button.)
- There's a language selector at the top of the sidebar (English (US) /
  Spanish (Latin America) / Brazilian Portuguese) — it translates the
  entire UI, including every Details popover and the generated briefing
  itself. Worth a quick mention if presenting to a LatAm/Brazil audience:
  *"this isn't just a translated label set — even the agent's narrated
  output comes back in whichever language you pick."* Defaults to English;
  switch it before clicking Generate if you want the briefing itself in
  another language, since that's baked into the API call at generation
  time (switching after generating a briefing won't retranslate it).

## Live walkthrough

**0. (Streamlit only) Log in with Okta before touching the app.**

> "Before I can even use this agent, I have to authenticate as myself
> through Okta — the agent isn't a standing service anyone can just open."

The *first* time anyone uses the HR or Ticketing connections, clicking
"Generate this week's briefing" opens a modal with a one-time **"Grant
access"** link instead of the briefing — that's expected, not a bug, and
it happens *separately* for each of the two (consent is per-resource).
The link **opens in a new tab on purpose** (Okta's consent screen can't be
embedded, and its redirect lands on an Okta-owned page, not back in this
app) — approve there, then just switch back to this tab: **it's already
polling in the background** and continues automatically the moment access
is granted, no second click needed. Worth narrating live if it happens:
*"That consent step you just saw is the org acknowledging, once, that I'm
allowed to let this agent see this system's data on my behalf — after
that, it's silent. And notice I didn't have to come back and click
anything again — the app's just watching for it."*

Before clicking, it's worth popping open the **"❓ MCP Server vs Resource
Server"** button on the front door — it's the quiet setup for the HR/
Ticketing contrast in step 1 below: *"Same underlying mechanism for both,
registered two different ways — I'll show you exactly which is which in a
second."*

**1. Before clicking Generate — walk through the "Which systems should the
agent connect to?" checkboxes.**

> "Before anything else, here's what's about to happen under the hood —
> and I can decide, live, which systems the agent actually touches."

Each checkbox already shows its `connection_type` underneath, and a
"Details" popover with the mechanism description *and* a pattern
diagram — all static, so you can walk through the whole story before ever
clicking Generate (a live token-expiry readout also shows up here once
you've generated a briefing at least once):
- **HR** — this is the one to slow down on: *"This isn't a service account
  with a bag of permissions — the agent just proved, cryptographically with
  its own signing key, who it is, and separately proved who I am, and Okta
  handed back one token with both facts in it. If you decoded that token
  right now you'd see two separate identities: the agent's client ID, and
  my own user ID. That's chain of custody — not 'something acted,' but
  'this specific agent acted on behalf of this specific person.' Client
  credentials alone can never give you that. This one's registered as a
  Resource Server — I told Okta by hand which authorization server
  protects it."*
- **Ticketing**: *"Exact same mechanism as HR — same chain of custody, same
  token shape, same consent step you just saw. The only difference is how
  Okta found out which authorization server protects it: this backend
  speaks the Model Context Protocol, so I registered it as an 'MCP Server'
  instead, and Okta auto-discovered the authorization server itself by
  calling a standard discovery endpoint on the backend — I never typed an
  endpoint URL in by hand. That's the practical tradeoff: less manual
  config, but Okta's cloud has to be able to reach the backend live at
  setup time to do that discovery."*
- **Finance**: *"This one's a live OAuth handshake against Okta, in real
  time, scoped to exactly one thing — `finance.read`, nothing else —
  expiring in an hour. If this agent gets compromised five minutes from
  now, that token is worthless in fifty-five minutes without anyone doing
  anything. No user context in this one, deliberately — a good contrast
  with HR and Ticketing."* (After generating a briefing, open Finance's
  Details popover and point at the live "valid for N more minutes"
  line — this isn't a claim, it's the actual token's real expiry, decoded
  right there.)
- **Analytics**: *"This system is older — no OAuth support at all, just a
  static API key. That's still most of what you actually have in
  production today. Instead of that key living in the agent's config file
  where any code review, log line, or breach exposes it, it's vaulted in
  Okta Privileged Access. The agent had to do a real-time encrypted
  handshake — generate a keypair, prove who it is, get the secret
  re-encrypted just for it — to read that key just now. It's never at rest
  anywhere the agent controls."*
- **Kudos Wall (leave unchecked, but worth opening the Details popover)**:
  *"This one's real Cross-App Access — a different IETF protocol than the
  STS mechanism HR and Ticketing use, and the resource runs its **own**
  authorization server instead of trusting Okta's directly. It's fully
  built and wired end-to-end — we're one Okta API Scopes declaration away
  from it working live. I've left it unchecked for today's run, but happy
  to walk through exactly where it stands."*

Worth opening the **"❓ MCP Server vs Resource Server"** button too — it's
the quiet setup for the HR/Ticketing contrast above: *"Same underlying
mechanism for both, registered two different ways — I'll show you exactly
which is which."* This isn't a one-off invention either: *"Okta's own
architecture team has already catalogued seven of these agentic-identity
patterns internally — each of these connections is a working instance of
one of them."* Full mapping and citation in `SETUP.md` §11.

**2. Click "Generate this week's briefing" and let it print.**

> "And this isn't just plumbing for its own sake — here's the actual
> output." (Let them read it. It's a genuinely coherent Monday briefing that
> cross-references data across systems — e.g. it may flag that someone with
> a pending time-off request is also the sole owner of a stalled ticket.)

**2b. Open the sidebar's "🔍 Live Okta ↔ MCP trace" panel.**

> "This is the part I'd show a security engineer, not just a security
> buyer." Every single HTTP call the agent just made — to Okta, to each
> backend — logged in order, with secrets redacted but token **claims
> decoded right there**. Expand one of the HR entries and point at the
> `cid`/`sub` pair in the decoded claims: *"There it is — the agent's
> identity and my identity, in the same token, and you're looking at the
> actual raw exchange, not a diagram of what it's supposed to do."* This is
> the single best "prove it" moment in the whole demo. Use "Clear trace" to
> reset between runs if you're demoing multiple times.

**3. Switch to the browser tab — the agent's page in Okta.**

> "Now here's the part a security team actually cares about. This agent
> isn't just running somewhere with a bag of credentials — it's a directory
> object. It has an owner. Its access is enumerated, not implied: a
> resource-server connection for HR scoped to `hr.read`, an MCP-server
> connection for Ticketing scoped to `ticketing.read` — both requiring user
> consent — an authorization-server connection for Finance scoped to
> `finance.read`, and a vaulted-secret connection for Analytics. A security
> team can look at this object and know, completely, what this agent can
> touch — without reading a line of its code."

**4. If asked "what if it goes rogue":**

> "That's the piece we didn't get to build in the time we had — a kill
> switch, revoking every one of these tokens/grants from this same page in
> one action. It's a natural next step given everything's already declared
> here, not a re-architecture."

Honest caveat if pressed on specifics: we actually looked into building a
"revoke consent" button for HR/Ticketing's one-time consent specifically,
and found there's **no documented Okta mechanism to revoke it today** —
it isn't tracked as a classic OAuth grant (confirmed live against the
Grants API), and neither the end-user self-service page nor the AI
Agent's own Admin Console object exposes it either. Not a demo blocker —
each *access token* still only lives an hour regardless (that part of the
kill-switch story, "worthless within the hour," holds up fine) — but the
underlying one-time *consent* itself has no revoke path yet. Good material
for "what's still rough about this feature" if an Okta PM is in the room,
an honest gap in tooling maturity for this specific consent type.

## Anticipated questions

- **"Is this real or a mockup?"** Real. Every OAuth token and every vaulted
  secret is live against an actual Okta tenant — nothing here is simulated.
  The *backend systems* (HR/Finance/Ticketing/Analytics) are sample/mock
  data, not the security mechanics.
- **"Does this work if the backend only has an API key, no OAuth at all?"**
  Yes — that's exactly what Analytics demonstrates. That's a common case in
  the field too, not just the OAuth-native systems.
- **"What's the effort to onboard a new resource?"** For the full
  user-context mechanism: register either a **Resource Server** (HR's
  path — ~3 console steps, reusing an existing authorization server and
  OAuth app, no reachability requirement) or an **MCP Server** (Ticketing's
  path — point Okta at the backend's URL and it auto-discovers the
  authorization server, but the backend must be reachable from Okta's
  cloud at registration time), then add a resource connection on the AI
  Agent — no new code either way beyond exposing the MCP discovery
  endpoint if you go that route. For a plain app-only OAuth resource
  (Finance's): one custom auth server + a scope + a policy (~4 API calls).
  For a legacy static-key resource: vault the key in OPA once, grant the
  agent's identity read access. See `SETUP.md`.
- **"Can this pattern work for [Salesforce / Zendesk / our internal
  system]?"** Yes — swap which backend each connection points at. The O4AA
  mechanics (the AI Agent token exchange for anything needing real user
  context, plain client_credentials for OAuth-capable resources that
  don't, OPA vaulting for the rest) are identical regardless of what data
  is on the other end. See "What this demo is NOT" below for the honest
  caveat on what would need to change.
- **"Is this real Cross-App Access (XAA), with the ID-JAG token exchange?"**
  For HR/Ticketing, no — those use Okta's **native AI Agent token exchange
  (OAuth STS)** (`SETUP.md` §9/§10), a different, Okta-specific mechanism
  that achieves the same practical outcome (real end-user identity in the
  token, no client_secret used). But we *also* have a fifth connection,
  **Kudos Wall, that IS real XAA** — the actual IETF
  `draft-ietf-oauth-identity-assertion-authz-grant` protocol, fully
  implemented and wired end-to-end (`SETUP.md` §12), currently paused one
  Okta API Scopes declaration short of working live. We spent a long time
  thinking it was blocked by a missing catalog integration — turned out
  Okta's own official XAA sample app pair was already installed on this
  tenant, just never enabled. Good material either way if a technical
  prospect (or an Okta PM) asks "have you actually tried real XAA" — the
  honest answer is yes, in detail, here's exactly where it stands today,
  and here's the STS alternative that's fully live in the meantime.
- **"What's different about how Kudos Wall's connection works?"** Every
  other connection here is validated by *Okta itself*. Kudos Wall's
  resource runs its **own** authorization server (`mcp-servers/kudos-wall-mcp/`)
  — Okta only mints a short-lived assertion (the ID-JAG); the resource
  verifies it against Okta's public keys and mints its own access token.
  That's the actual architectural difference real XAA introduces, and it's
  worth drawing on a whiteboard if asked — see the full architecture
  diagram ("🗺️ Full architecture diagram" button in the sidebar) or
  `SETUP.md` §12.

## What this demo is NOT

Be upfront about this rather than let a technical prospect discover it:

- **The data is internal-ops, not customer/account data.** The backend
  systems are Okta's own O4AA sample MCP servers, modeling a company's *own*
  HR/Finance/Ticketing/Analytics/Kudos systems (a Monday standup briefing),
  not a CRM or account-research tool. If a prospect's use case is closer to
  account/customer research, say so and pivot the narrative: *"same
  architecture, different backend — point these same mechanisms at
  Salesforce and a support tool instead, and you get an account-briefing
  agent instead of a standup agent."* Don't claim it already does that.
- **Kudos Wall (real XAA) isn't live yet**, just fully built and one config
  step from it — be precise about this distinction if asked; don't imply
  it's running today.
- **No kill switch demo yet.** Governance is shown as declared state (what
  the agent can touch), not as a live revocation action.
- **No access-certification campaign wired up.** Also a natural next step,
  not yet built.
