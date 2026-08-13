"""Streamlit front end for the Monday Briefing Agent demo.

Usage: streamlit run app.py
"""

import base64
import json
import time
import uuid
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from auth import (
    build_agent0_authorize_url,
    build_authorize_url,
    clear_saved_agent0_id_token,
    clear_saved_user,
    consume_agent0_pending_state,
    consume_pending_state,
    exchange_agent0_code_for_id_token,
    exchange_code_for_userinfo,
    get_saved_agent0_id_token,
    get_saved_user,
    save_agent0_id_token,
    save_user,
)
from call_log import clear as clear_call_log, get_log
from i18n import LANGUAGES, current_lang, get_saved_language, rt, save_language, t
from main import gather_briefing_data, narrate
from okta_auth import ConsentRequired, SessionExpired
from resources import RESOURCES

load_dotenv()

st.set_page_config(page_title="Monday Briefing Agent", page_icon="🗓️", layout="wide")

# Trim Streamlit's default top padding in both the main area and sidebar --
# pure cosmetics, no functional effect.
st.markdown(
    """
    <style>
    .block-container { padding-top: 1.5rem !important; }
    section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] { gap: 0.5rem; }
    [data-testid="stSidebarContent"] { padding-top: 1.5rem !important; }
    /* Make popover/dialog content scroll instead of getting clipped when
       it's taller than the viewport -- e.g. an expanded diagram. Scoped
       to content *inside* a popover or dialog specifically (not every
       stVerticalBlock site-wide) -- applying this to the page's top-level
       vertical block capped the whole page at 80vh and left dead space
       below it, pushing the visible bottom of the page up. */
    [data-testid="stPopoverBody"] [data-testid="stVerticalBlock"],
    [data-testid="stDialog"] [data-testid="stVerticalBlock"] {
        max-height: 80vh !important;
        overflow-y: auto !important;
        overflow-x: auto !important;
    }
    /* The diagram popup (st.dialog) is opened from a button inside a
       popover (the "Details" popover, or the sidebar's architecture
       button). Both popovers and dialogs render as role="dialog"
       overlays, but the popover's floating-overlay portal defaults to a
       higher z-index than the modal -- without this override, a dialog
       opened from inside a popover renders visually behind it. Force the
       modal (and its portal wrapper) to the top of the stack. */
    [data-testid="stDialog"],
    div:has(> [data-testid="stDialog"]),
    body > div:has([data-testid="stDialog"]) {
        z-index: 2147483647 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    _lang_names = list(LANGUAGES.keys())
    _lang_codes = list(LANGUAGES.values())
    if "lang" not in st.session_state:
        # A hard refresh starts a fresh session (session_state reset), so
        # on first render of a session, restore from the process-level
        # cache instead of defaulting back to English.
        _restored = get_saved_language()
        st.session_state["lang"] = _restored if _restored in _lang_codes else "en"
    _current_code = st.session_state["lang"]
    _choice = st.selectbox(
        t("language_label"),
        options=_lang_names,
        index=_lang_codes.index(_current_code),
        key="lang_selector",
    )
    st.session_state["lang"] = LANGUAGES[_choice]
    save_language(st.session_state["lang"])

ARCHITECTURE_DIAGRAM = Path(__file__).parent / "assets" / "architecture.png"
RESOURCE_ICONS = {"hr": "🪪", "ticketing": "🛰️", "finance": "🔑", "analytics": "🔒", "kudos": "🎉"}
RESOURCE_COLORS = {"hr": "#4C8BF5", "ticketing": "#20B2AA", "finance": "#F5A623", "analytics": "#9B59B6", "kudos": "#E85D75"}

# Pattern diagram images, keyed by resource -- the display name for each
# now comes from i18n.rt(key, "pattern_name") instead of living here.
PATTERNS_DIR = Path(__file__).parent / "assets" / "patterns"
PATTERN_IMAGES = {
    "hr": PATTERNS_DIR / "hr.png",
    "ticketing": PATTERNS_DIR / "ticketing.png",
    "finance": PATTERNS_DIR / "finance.png",
    "analytics": PATTERNS_DIR / "analytics.png",
    "kudos": PATTERNS_DIR / "kudos.png",
}


def _image_data_uri(path: Path) -> str:
    """Base64 data: URI for a local PNG -- lets a components.html() srcdoc
    iframe render it directly (its relative-URL resolution has nothing to
    do with this app's server), with zero server-side re-encoding/resizing
    in between, unlike routing it through st.image()'s media endpoint."""
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def _render_zoomable_image(data_uri: str, height: int = 650):
    """Pan/zoom viewer for a diagram at full native resolution: fits the
    whole image on load, then scroll-wheel (zoom at cursor), click-drag
    (pan), double-click (zoom step), and +/-/reset controls to inspect
    detail beyond what fitting the dialog would otherwise show. The image
    itself is only ever displayed, never resampled by this viewer -- the
    PNG's own resolution is the ceiling on "quality," this just stops the
    dialog's layout from being the ceiling too."""
    viewer_id = uuid.uuid4().hex
    components.html(
        f"""
        <div id="stage-{viewer_id}" style="position:relative;width:100%;height:{height}px;
            overflow:hidden;background:#0e1117;border-radius:8px;cursor:grab;">
          <div style="position:absolute;top:8px;right:8px;z-index:10;display:flex;gap:6px;
              align-items:center;font-family:inherit;">
            <span id="label-{viewer_id}" style="color:#fafafa;background:rgba(0,0,0,0.55);
                padding:0.25em 0.6em;border-radius:0.4em;font-size:0.85rem;">100%</span>
            <button id="out-{viewer_id}" title="Zoom out" style="{_ZOOM_BTN_STYLE}">−</button>
            <button id="reset-{viewer_id}" title="Fit to view" style="{_ZOOM_BTN_STYLE}">⤢</button>
            <button id="in-{viewer_id}" title="Zoom in" style="{_ZOOM_BTN_STYLE}">+</button>
          </div>
          <img id="img-{viewer_id}" src="{data_uri}" draggable="false"
              style="position:absolute;top:0;left:0;transform-origin:0 0;user-select:none;" />
        </div>
        <script>
        (function() {{
            const stage = document.getElementById("stage-{viewer_id}");
            const img = document.getElementById("img-{viewer_id}");
            const label = document.getElementById("label-{viewer_id}");
            let scale = 1, fitScale = 1, tx = 0, ty = 0, dragging = false, sx, sy, stx, sty;

            function apply() {{
                img.style.transform = `translate(${{tx}}px, ${{ty}}px) scale(${{scale}})`;
                label.textContent = Math.round((scale / fitScale) * 100) + "%";
            }}

            function fit() {{
                const cw = stage.clientWidth, ch = stage.clientHeight;
                const iw = img.naturalWidth, ih = img.naturalHeight;
                fitScale = Math.min(cw / iw, ch / ih);
                scale = fitScale;
                tx = (cw - iw * scale) / 2;
                ty = (ch - ih * scale) / 2;
                apply();
            }}
            if (img.complete) fit(); else img.onload = fit;

            function zoomAt(factor, clientX, clientY) {{
                const rect = stage.getBoundingClientRect();
                const cx = clientX - rect.left, cy = clientY - rect.top;
                const next = Math.min(Math.max(scale * factor, fitScale * 0.4), Math.max(4, fitScale * 10));
                tx = cx - (cx - tx) * (next / scale);
                ty = cy - (cy - ty) * (next / scale);
                scale = next;
                apply();
            }}

            stage.addEventListener("wheel", (e) => {{
                e.preventDefault();
                zoomAt(e.deltaY < 0 ? 1.15 : 1 / 1.15, e.clientX, e.clientY);
            }}, {{ passive: false }});
            stage.addEventListener("dblclick", (e) => zoomAt(1.8, e.clientX, e.clientY));
            stage.addEventListener("mousedown", (e) => {{
                dragging = true; sx = e.clientX; sy = e.clientY; stx = tx; sty = ty;
                stage.style.cursor = "grabbing";
            }});
            window.addEventListener("mousemove", (e) => {{
                if (!dragging) return;
                tx = stx + (e.clientX - sx); ty = sty + (e.clientY - sy);
                apply();
            }});
            window.addEventListener("mouseup", () => {{ dragging = false; stage.style.cursor = "grab"; }});

            document.getElementById("in-{viewer_id}").onclick = () => {{
                const r = stage.getBoundingClientRect();
                zoomAt(1.4, r.left + r.width / 2, r.top + r.height / 2);
            }};
            document.getElementById("out-{viewer_id}").onclick = () => {{
                const r = stage.getBoundingClientRect();
                zoomAt(1 / 1.4, r.left + r.width / 2, r.top + r.height / 2);
            }};
            document.getElementById("reset-{viewer_id}").onclick = fit;
        }})();
        </script>
        """,
        height=height,
    )


_ZOOM_BTN_STYLE = (
    "background:rgba(255,255,255,0.9);color:#0e1117;border:none;border-radius:0.4em;"
    "width:1.8em;height:1.8em;font-size:1rem;font-weight:700;cursor:pointer;line-height:1;"
)


@st.dialog(t("expand_diagram"), width="large")
def _show_pattern_diagram(image_path, pattern_name):
    st.caption(f"🗺️ {pattern_name}")
    # No width cap -- native size/quality, same treatment as the
    # architecture diagram's popup.
    st.image(str(image_path))


def require_login():
    if "user" in st.session_state:
        return

    # st.session_state doesn't reliably survive a full-page round trip to
    # an external domain and back -- recover from the module-level cache
    # (see auth.save_user) before assuming nobody's logged in and treating
    # any incoming code/state as a fresh Front Door login attempt. Without
    # this, a LATER external round trip for a *different* flow (e.g. the
    # Agent0 login below) looks like a failed Front Door login instead.
    saved = get_saved_user()
    if saved is not None:
        st.session_state["user"] = saved
        return

    params = st.query_params
    if "code" in params:
        if not consume_pending_state(params.get("state")):
            st.error(t("login_error_state_mismatch"))
            st.query_params.clear()
            st.stop()
        user = exchange_code_for_userinfo(params["code"])
        st.session_state["user"] = user
        save_user(user)
        st.query_params.clear()
        st.rerun()

    st.title("🗓️ Monday Briefing Agent")
    st.caption(t("sign_in_prompt"))
    login_message = st.session_state.pop("login_message", None)
    if login_message:
        st.warning(login_message)
    # st.link_button always opens target="_blank" with no way to override it,
    # which breaks this redirect-back-to-the-same-tab flow -- use a plain
    # anchor tag forced to the same tab instead.
    st.markdown(
        f'<a href="{build_authorize_url()}" target="_self" '
        'style="display:inline-block;padding:0.5em 1em;background:#FF4B4B;'
        'color:white;border-radius:0.5em;text-decoration:none;font-weight:600;">'
        f"{t('login_button')}</a>",
        unsafe_allow_html=True,
    )
    st.stop()


require_login()
user = st.session_state["user"]

# Separate, on-demand login through Agent0 (the XAA Requester app) --
# real Cross-App Access needs an id_token whose `aud` is Agent0 itself,
# distinct from the main login's id_token used for HR/Ticketing STS. Only
# triggered when Kudos Wall is about to be used (see the button below),
# but the callback can land here any time after that, so it's checked
# unconditionally, same shape as require_login()'s own callback handling.
# Restored from the module-level cache first for the same reason as
# require_login() above -- this round trip loses st.session_state too.
if "agent0_id_token" not in st.session_state and get_saved_agent0_id_token() is not None:
    st.session_state["agent0_id_token"] = get_saved_agent0_id_token()

agent0_params = st.query_params
if "code" in agent0_params and consume_agent0_pending_state(agent0_params.get("state")):
    token = exchange_agent0_code_for_id_token(agent0_params["code"])
    st.session_state["agent0_id_token"] = token
    save_agent0_id_token(token)
    st.query_params.clear()
    st.rerun()


def _handle_session_expired():
    """Our own login cache (auth.save_user/get_saved_user) never checks
    whether the underlying Okta session is still alive -- it just trusts a
    cached user indefinitely. If the user force-logs-out from Okta's own
    end-user dashboard, this app has no way to know until its next token
    exchange fails with SessionExpired. Clear everything cached and route
    back to the login screen instead of surfacing a raw HTTP error."""
    clear_saved_user()
    if "user" in st.session_state:
        del st.session_state["user"]
    clear_saved_agent0_id_token()
    if "agent0_id_token" in st.session_state:
        del st.session_state["agent0_id_token"]
    st.session_state["login_message"] = t("session_expired_message")
    st.rerun()


@st.dialog(t("architecture_expander"), width="large")
def _show_architecture_diagram():
    if ARCHITECTURE_DIAGRAM.exists():
        st.caption(t("architecture_zoom_hint"))
        _render_zoomable_image(_image_data_uri(ARCHITECTURE_DIAGRAM), height=650)
    else:
        st.caption(t("architecture_missing"))


CONSENT_POLL_INTERVAL_SECONDS = 3
CONSENT_POLL_TIMEOUT_SECONDS = 90


def _render_consent_link(resource_label, url, link_text):
    """Renders the "Grant access" button via a real window.open() (instead
    of a plain <a target="_blank">) and stashes the resulting window handle
    on the top-level app window (window.parent from inside this component's
    srcdoc iframe -- same-origin, so this is allowed) keyed by resource
    label. That handle is what lets _close_consent_popup() below close this
    tab later purely from the opener side -- we can never reach into the
    popup's own content to auto-close it, since its post-consent redirect
    lands on an Okta-owned URL we don't control (see _run_consent_flow's
    docstring)."""
    button_id = "grant-" + uuid.uuid4().hex
    components.html(
        f"""
        <button id="{button_id}" style="display:inline-block;padding:0.5em 1em;background:#FF4B4B;
            color:white;border:none;border-radius:0.5em;font-weight:600;
            font-size:1rem;font-family:inherit;cursor:pointer;">
            {link_text}
        </button>
        <script>
        document.getElementById({json.dumps(button_id)}).addEventListener("click", function() {{
            window.parent.__consentPopups = window.parent.__consentPopups || {{}};
            window.parent.__consentPopups[{json.dumps(resource_label)}] =
                window.open({json.dumps(url)}, {json.dumps("consent_" + resource_label)});
        }});
        </script>
        """,
        height=50,
    )


def _close_consent_popup(resource_label):
    """Closes the popup opened for resource_label, if still open. Cross-origin
    windows can't be inspected, but a WindowProxy's own close() is one of the
    few operations still allowed across origins -- so this works even though
    the popup is by now showing Okta's own post-consent page."""
    if not resource_label:
        return
    components.html(
        f"""
        <script>
        (function() {{
            const popups = window.parent.__consentPopups;
            const w = popups && popups[{json.dumps(resource_label)}];
            if (w) {{
                try {{ w.close(); }} catch (e) {{}}
                delete popups[{json.dumps(resource_label)}];
            }}
        }})();
        </script>
        """,
        height=0,
    )


@st.dialog(t("consent_dialog_title"))
def _run_consent_flow(selected_keys):
    """Okta's hosted consent screen can't be embedded here (it blocks
    iframing, same as any IdP login page) and its post-consent redirect
    goes to an Okta-owned URL, not back into this app -- so the actual
    "approve" click unavoidably happens in another tab. What we CAN do:
    retry the token exchange automatically in the background (retrying
    the exact same call is exactly how a human would "check again" by
    hand) so the user never has to come back and click Generate a second
    time. See SETUP.md §9's STS gotchas for why the redirect can't target
    this app directly."""
    explanation_area = st.empty()
    status_area = st.empty()
    shown_resource = None
    deadline = time.time() + CONSENT_POLL_TIMEOUT_SECONDS

    while True:
        try:
            data, receipts, token_expiry = gather_briefing_data(
                subject_id_token=user["_id_token"],
                agent0_id_token=st.session_state.get("agent0_id_token"),
                selected=selected_keys,
            )
        except SessionExpired:
            _handle_session_expired()
        except ConsentRequired as e:
            if e.resource_label != shown_resource:
                if shown_resource is not None:
                    # A different resource is now asking for consent, which
                    # only happens once the previous one succeeded (HR then
                    # Ticketing) -- close its now-stale popup automatically.
                    _close_consent_popup(shown_resource)
                shown_resource = e.resource_label
                deadline = time.time() + CONSENT_POLL_TIMEOUT_SECONDS  # fresh window per resource
                explanations = {
                    RESOURCES["hr"]["connection_type"]: t("consent_explanation_sts_resource"),
                    RESOURCES["ticketing"]["connection_type"]: t("consent_explanation_sts_mcp"),
                }
                with explanation_area.container():
                    st.warning(t("consent_warning").format(resource=e.resource_label))
                    st.markdown(explanations.get(e.connection_type, t("consent_explanation_default")))
                    st.caption(t("consent_contrast_caption"))
                    st.info(t("consent_info_new_tab"))
                    _render_consent_link(e.resource_label, e.interaction_uri, t("grant_access_link"))
            if time.time() > deadline:
                status_area.warning(t("consent_timeout_fallback"))
                return
            status_area.caption(t("consent_waiting_status").format(resource=e.resource_label))
            time.sleep(CONSENT_POLL_INTERVAL_SECONDS)
            continue

        # Reaching here means the retry succeeded with no ConsentRequired at
        # all -- if a popup was open for whichever resource was asked last,
        # its access has just been granted, so close it automatically too.
        _close_consent_popup(shown_resource)
        status_area.empty()
        with st.spinner(t("narrating_spinner")):
            briefing = narrate(data, lang=current_lang())
        st.session_state["last_briefing"] = briefing
        st.session_state["last_briefing_data"] = data
        st.session_state["last_token_expiry"] = token_expiry
        st.rerun()


with st.sidebar:
    st.write(t("signed_in_as").format(name=user.get("name", user.get("email"))))
    if st.button(t("logout_button")):
        del st.session_state["user"]
        clear_saved_user()
        if "agent0_id_token" in st.session_state:
            del st.session_state["agent0_id_token"]
        clear_saved_agent0_id_token()
        st.rerun()
    if st.button(t("architecture_expander")):
        _show_architecture_diagram()

st.title("🗓️ Monday Briefing Agent")
st.caption(t("caption_secured"))

with st.popover(t("mcp_vs_resource_popover")):
    st.markdown(t("mcp_vs_resource_body"))

st.subheader(t("systems_subheader"))
pattern_toggles = {}
toggle_cols = st.columns(5)
for col, key in zip(toggle_cols, ["hr", "ticketing", "finance", "analytics", "kudos"]):
    r = RESOURCES[key]
    color = RESOURCE_COLORS[key]
    with col:
        with st.container(border=True, height=320):
            short_label = rt(key, "label")
            st.markdown(
                f'<div style="background:{color};color:white;padding:6px 12px;'
                'border-radius:8px;font-weight:700;text-align:center;margin-bottom:10px;">'
                f'{RESOURCE_ICONS[key]} {short_label}'
                f'{t("paused_suffix") if key == "kudos" else ""}</div>',
                unsafe_allow_html=True,
            )
            default_on = key != "kudos"
            pattern_toggles[key] = st.checkbox(t("include_checkbox"), value=default_on, key=f"toggle_{key}")
            st.markdown(
                f'<span style="color:{color};font-weight:600;">{rt(key, "connection_type")}</span>',
                unsafe_allow_html=True,
            )
            with st.popover(t("details_popover"), use_container_width=True):
                st.caption(rt(key, "mechanism"))
                st.markdown(rt(key, "when_to_use"))

                expiry_map = st.session_state.get("last_token_expiry", {})
                if key in expiry_map:
                    exp = expiry_map[key]
                    if exp is not None:
                        remaining_min = max(0, int((exp - time.time()) / 60))
                        expires_at = time.strftime("%H:%M:%S", time.localtime(exp))
                        st.caption(t("token_ttl_valid").format(minutes=remaining_min, time=expires_at))
                    else:
                        st.caption(t("token_ttl_no_fixed"))
                else:
                    st.caption(t("token_ttl_not_yet"))

                image = PATTERN_IMAGES.get(key)
                if image:
                    st.caption(f"🗺️ {rt(key, 'pattern_name')}")
                    if image.exists():
                        st.image(str(image), width=280)
                        if st.button(t("expand_diagram"), key=f"expand_btn_{key}"):
                            _show_pattern_diagram(image, rt(key, "pattern_name"))
selected_keys = {key for key, checked in pattern_toggles.items() if checked}

if st.button(t("generate_button"), type="primary"):
    if "kudos" in selected_keys and "agent0_id_token" not in st.session_state:
        st.warning(t("kudos_login_warning"))
        # Same target="_self" workaround as the main login link (app.py's
        # require_login()) -- this redirect_uri comes back to THIS app (not
        # an Okta-owned page like the STS consent flow), so it must land in
        # the same browser tab/session for st.session_state to see it.
        st.markdown(
            f'<a href="{build_agent0_authorize_url()}" target="_self" '
            'style="display:inline-block;padding:0.5em 1em;background:#FF4B4B;'
            'color:white;border-radius:0.5em;text-decoration:none;font-weight:600;">'
            f"{t('kudos_login_button')}</a>",
            unsafe_allow_html=True,
        )
        st.caption(t("kudos_login_caption"))
        st.stop()

    if not selected_keys:
        st.info(t("select_at_least_one"))
        st.stop()

    clear_call_log()
    try:
        with st.spinner(t("connecting_spinner").format(systems=", ".join(sorted(selected_keys)))):
            data, receipts, token_expiry = gather_briefing_data(
                subject_id_token=user["_id_token"],
                agent0_id_token=st.session_state.get("agent0_id_token"),
                selected=selected_keys,
            )
    except SessionExpired:
        _handle_session_expired()
    except ConsentRequired:
        # The dialog redoes this exact call as its first poll attempt --
        # see _run_consent_flow's docstring for why it can't just resume
        # from here directly.
        _run_consent_flow(selected_keys)
        st.stop()

    with st.spinner(t("narrating_spinner")):
        briefing = narrate(data, lang=current_lang())

    # Store instead of rendering directly here -- this block only runs on
    # the exact rerun triggered by this button's click. Any *other* widget
    # (the language selector, a checkbox) also triggers a rerun, and on
    # that rerun st.button() is False, so rendering only happened here
    # would make the briefing vanish the moment anything else was touched.
    st.session_state["last_briefing"] = briefing
    st.session_state["last_briefing_data"] = data
    st.session_state["last_token_expiry"] = token_expiry

if "last_briefing" in st.session_state:
    st.subheader(t("briefing_subheader"))
    st.markdown(st.session_state["last_briefing"])

    with st.expander(t("raw_data_expander")):
        st.json(st.session_state["last_briefing_data"])
else:
    st.info(t("click_button_info"))

with st.sidebar:
    st.divider()
    st.subheader(t("sidebar_trace_subheader"))
    st.caption(t("sidebar_trace_caption"))
    trace = get_log()
    if trace and st.button(t("clear_trace_button")):
        clear_call_log()
        st.rerun()
    if not trace:
        st.caption(t("sidebar_trace_empty"))
    else:
        for i, entry in enumerate(trace):
            ok = entry["status_code"] < 400
            with st.expander(f"{'✅' if ok else '❌'} {entry['time']} — {entry['label']}"):
                st.caption(f"`{entry['method']}` {entry['url']}")
                if entry["request"]:
                    st.markdown(t("trace_request_label"))
                    st.json(entry["request"])
                if entry["headers"]:
                    st.markdown(t("trace_headers_label"))
                    st.json(entry["headers"])
                st.markdown(t("trace_response_label").format(status=entry["status_code"]))
                if entry["response"] == "":
                    # e.g. a 204 No Content -- st.json() on an empty
                    # string tries to JSON-parse it client-side and fails
                    # with a confusing "Unexpected EOF" error.
                    st.caption(t("trace_response_empty"))
                else:
                    st.json(entry["response"])
