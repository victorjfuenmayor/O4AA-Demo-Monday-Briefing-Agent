"""Streamlit front end for the Monday Briefing Agent demo.

Usage: streamlit run app.py
"""

import streamlit as st
from dotenv import load_dotenv

from auth import build_authorize_url, consume_pending_state, exchange_code_for_userinfo
from main import gather_briefing_data, narrate

load_dotenv()

st.set_page_config(page_title="Monday Briefing Agent", page_icon="🗓️", layout="centered")


def require_login():
    if "user" in st.session_state:
        return

    params = st.query_params
    if "code" in params:
        if not consume_pending_state(params.get("state")):
            st.error("Login failed: state mismatch. Try logging in again.")
            st.query_params.clear()
            st.stop()
        st.session_state["user"] = exchange_code_for_userinfo(params["code"])
        st.query_params.clear()
        st.rerun()

    st.title("🗓️ Monday Briefing Agent")
    st.caption("Sign in with your Okta account to continue.")
    # st.link_button always opens target="_blank" with no way to override it,
    # which breaks this redirect-back-to-the-same-tab flow -- use a plain
    # anchor tag forced to the same tab instead.
    st.markdown(
        f'<a href="{build_authorize_url()}" target="_self" '
        'style="display:inline-block;padding:0.5em 1em;background:#FF4B4B;'
        'color:white;border-radius:0.5em;text-decoration:none;font-weight:600;">'
        "Log in with Okta</a>",
        unsafe_allow_html=True,
    )
    st.stop()


require_login()
user = st.session_state["user"]

with st.sidebar:
    st.write(f"Signed in as **{user.get('name', user.get('email'))}**")
    if st.button("Log out"):
        del st.session_state["user"]
        st.rerun()

st.title("🗓️ Monday Briefing Agent")
st.caption("Every connection below is secured end-to-end by Okta for AI Agents (O4AA).")

if st.button("Generate this week's briefing", type="primary"):
    with st.spinner("Connecting to HR, Finance, Ticketing, and Analytics systems..."):
        data, receipts = gather_briefing_data()

    st.subheader("O4AA Resource Connection Receipts")
    icon = {
        "Authorization server (OAuth client_credentials)": "🔑",
        "Vaulted secret (OPA / static key)": "🔒",
    }
    cols = st.columns(len(receipts))
    for col, (label, connection_type, mechanism) in zip(cols, receipts):
        with col:
            st.markdown(f"**{icon.get(connection_type, '•')} {label}**")
            st.caption(connection_type)
            st.caption(mechanism)

    with st.spinner("Narrating..."):
        briefing = narrate(data)

    st.subheader("This Week's Briefing")
    st.markdown(briefing)

    with st.expander("Raw data pulled from each system"):
        st.json(data)
else:
    st.info("Click the button to run the agent live against ligalac.okta.com.")
