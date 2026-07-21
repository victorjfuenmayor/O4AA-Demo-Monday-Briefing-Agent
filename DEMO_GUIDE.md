# Demo Guide — pitching O4AA with the Monday Briefing Agent

For SEs driving the keyboard and AEs narrating. This demo proves a specific,
narrow claim well: **one agent, four backend systems, two completely
different auth postures, one governed control plane.** Don't oversell it as
more than that — see "What this demo is NOT" below.

## The one-sentence pitch

"Watch an AI agent pull real data from four different backend systems — two
that speak modern OAuth, two that only understand an old static API key —
and notice that at no point does the agent's code contain a single
credential. Everything it can touch, and everything it's allowed to do, is
declared and governed in Okta."

## Before you start

- All four MCP servers running (`SETUP.md` step 6), agent's `.env` filled in.
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

## Live walkthrough

**0. (Streamlit only) Log in with Okta before touching the app.**

> "Before I can even use this agent, I have to authenticate as myself
> through Okta — the agent isn't a standing service anyone can just open."

**1. Click "Generate this week's briefing" (or run `python main.py` for the CLI) and let the Receipts panel render.**

> "Before anything else, here's what just happened under the hood."

Point at each of the four lines:
- HR and Finance: *"These two connections weren't a hardcoded key sitting in
  the agent's code — the agent just did a live OAuth handshake against
  Okta, in real time, and got back a token scoped to exactly one thing —
  `hr.read`, nothing else — expiring in an hour. If this agent gets
  compromised five minutes from now, that token is worthless in fifty-five
  minutes without anyone doing anything."*
- Ticketing and Analytics: *"These two systems are older — no OAuth support
  at all, just a static API key. That's most of what you actually have in
  production today. Instead of that key living in the agent's config file
  where any code review, log line, or breach exposes it, it's vaulted in
  Okta Privileged Access. The agent had to do a real-time encrypted
  handshake — generate a keypair, prove who it is, get the secret
  re-encrypted just for it — to read that key just now. It's never at rest
  anywhere the agent controls."*

**2. Let the narrated briefing print.**

> "And this isn't just plumbing for its own sake — here's the actual
> output." (Let them read it. It's a genuinely coherent Monday briefing that
> cross-references data across systems — e.g. it may flag that someone with
> a pending time-off request is also the sole owner of a stalled ticket.)

**3. Switch to the browser tab — the agent's page in Okta.**

> "Now here's the part a security team actually cares about. This agent
> isn't just running somewhere with a bag of credentials — it's a directory
> object. It has an owner. Its access is enumerated, not implied: two
> resource connections scoped to exactly the two OAuth scopes it needs, and
> one vaulted-secret connection for the legacy systems. A security team can
> look at this object and know, completely, what this agent can touch —
> without reading a line of its code."

**4. If asked "what if it goes rogue":**

> "That's the piece we didn't get to build in the time we had — a kill
> switch, revoking every one of these tokens/grants from this same page in
> one action. It's a natural next step given everything's already declared
> here, not a re-architecture."

## Anticipated questions

- **"Is this real or a mockup?"** Real. Every OAuth token and every vaulted
  secret is live against an actual Okta tenant — nothing here is simulated.
  The *backend systems* (HR/Finance/Ticketing/Analytics) are sample/mock
  data, not the security mechanics.
- **"Does this work if the backend only has an API key, no OAuth at all?"**
  Yes — that's exactly what Ticketing and Analytics demonstrate. That's the
  more common case in the field, not the exception.
- **"What's the effort to onboard a new resource?"** For an OAuth-capable
  resource: one custom auth server + a scope + a policy (~4 API calls). For
  a legacy static-key resource: vault the key in OPA once, grant the
  agent's identity read access. See `SETUP.md`.
- **"Can this pattern work for [Salesforce / Zendesk / our internal
  system]?"** Yes — swap which backend each connection points at. The O4AA
  mechanics (client_credentials for OAuth-capable resources, OPA vaulting
  for the rest) are identical regardless of what data is on the other end.
  See "What this demo is NOT" below for the honest caveat on what would
  need to change.
- **"Is this real Cross-App Access (XAA), with the ID-JAG token exchange?"**
  Not in what's running today — HR and Finance both use plain OAuth
  `client_credentials` (app-only, no end-user identity in the token). We
  did fully implement and test real XAA (the actual
  `draft-ietf-oauth-identity-assertion-authz-grant` protocol) against this
  same tenant, and traced it precisely to a missing "XAA Resource App"
  catalog integration that this org doesn't have — a real platform gap,
  documented in `SETUP.md` §8, not a shortcut we took. Good material if a
  technical prospect (or an Okta PM) asks "have you actually tried real
  XAA" — the honest answer is yes, in detail, and here's exactly where it
  stops working today.

## What this demo is NOT

Be upfront about this rather than let a technical prospect discover it:

- **The data is internal-ops, not customer/account data.** The four backend
  systems are Okta's own O4AA sample MCP servers, modeling a company's *own*
  HR/Finance/Ticketing/Analytics systems (a Monday standup briefing), not a
  CRM or account-research tool. If a prospect's use case is closer to
  account/customer research, say so and pivot the narrative: *"same
  architecture, different backend — point these same two mechanisms at
  Salesforce and a support tool instead, and you get an account-briefing
  agent instead of a standup agent."* Don't claim it already does that.
- **No kill switch demo yet.** Governance is shown as declared state (what
  the agent can touch), not as a live revocation action.
- **No access-certification campaign wired up.** Also a natural next step,
  not yet built.
