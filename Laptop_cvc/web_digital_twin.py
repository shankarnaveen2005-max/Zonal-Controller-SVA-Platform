"""Public Streamlit SVA Digital Twin with authentication and audit logging."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import streamlit as st


APP_DIR = Path(__file__).resolve().parent
AUDIT_DB = Path(os.getenv("SVA_AUDIT_DB", APP_DIR / "sva_audit.db"))
ROLES = ("ADMIN", "ENGINEER", "VIEWER")

st.set_page_config(
    page_title="SVA Digital Twin",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp { background: #101820; color: #e8f1f5; }
    [data-testid="stHeader"] { background: #101820; }
    [data-testid="stSidebar"] { background: #1b2935; }
    .sva-card { background: #1b2935; border: 1px solid #395361;
      border-radius: 12px; padding: 18px; min-height: 150px; }
    .sva-title { color: #6dd5fa; font-size: 2rem; font-weight: 700; }
    .sva-muted { color: #9bb0b8; }
    .online { color: #27c281; font-weight: 700; }
    .warning { color: #f3b33d; font-weight: 700; }
    .offline { color: #ef6262; font-weight: 700; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets[name])
    except (KeyError, FileNotFoundError):
        return os.getenv(name, default)


def _audit(event: str, user_id: str = "anonymous", detail: str = "") -> None:
    """Write security-relevant events without ever storing passwords."""
    AUDIT_DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(AUDIT_DB) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS access_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_time TEXT NOT NULL,
                user_id TEXT NOT NULL,
                event TEXT NOT NULL,
                detail TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO access_log(event_time,user_id,event,detail) VALUES(?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), user_id, event, detail[:240]),
        )


def _users() -> dict[str, dict[str, str]]:
    raw = _secret("SVA_USERS_JSON")
    if not raw:
        return {}
    try:
        configured = json.loads(raw)
    except json.JSONDecodeError:
        st.error("SVA_USERS_JSON is invalid JSON. Contact the administrator.")
        return {}
    if not isinstance(configured, dict):
        st.error("SVA_USERS_JSON must be a JSON object.")
        return {}
    return {
        str(user_id): value
        for user_id, value in configured.items()
        if isinstance(value, dict)
        and value.get("role") in ROLES
        and isinstance(value.get("password_hash"), str)
    }


def _verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = encoded_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        expected = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
        return hmac.compare_digest(expected.hex(), digest_hex)
    except (TypeError, ValueError):
        return False


def _login() -> None:
    st.markdown(
        '<div class="sva-title">🚗 SVA DIGITAL TWIN</div>'
        '<p class="sva-muted">Secure zonal vehicle architecture platform</p>',
        unsafe_allow_html=True,
    )
    st.divider()
    _, card, _ = st.columns([1, 2, 1])
    with card:
        st.subheader("SVA LOGIN")
        if not _users():
            st.warning(
                "Authentication is not configured. Set SVA_USERS_JSON in the "
                "deployment secrets before publishing this application."
            )
            return
        with st.form("login_form"):
            user_id = st.text_input("User ID", autocomplete="username")
            password = st.text_input(
                "Password", type="password", autocomplete="current-password"
            )
            submitted = st.form_submit_button("LOGIN", use_container_width=True)
        if submitted:
            user = _users().get(user_id)
            if user and _verify_password(password, user["password_hash"]):
                st.session_state.authenticated = True
                st.session_state.user_id = user_id
                st.session_state.role = user["role"]
                _audit("LOGIN_SUCCESS", user_id, user["role"])
                st.rerun()
            _audit("LOGIN_FAILURE", user_id or "anonymous", "invalid credentials")
            st.error("Access denied. Check your User ID and password.")


def _logout() -> None:
    user_id = st.session_state.get("user_id", "anonymous")
    _audit("LOGOUT", user_id)
    for key in ("authenticated", "user_id", "role"):
        st.session_state.pop(key, None)
    st.rerun()


def _metric_card(label: str, value: str, state: str = "online") -> None:
    st.markdown(
        f'<div class="sva-card"><div class="sva-muted">{label}</div>'
        f'<h3 class="{state}">{value}</h3></div>',
        unsafe_allow_html=True,
    )


def _dashboard() -> None:
    user_id = st.session_state["user_id"]
    role = st.session_state["role"]
    with st.sidebar:
        st.markdown("### SVA DIGITAL TWIN")
        st.markdown(f"**User:** `{user_id}`")
        st.markdown(f"**Role:** `{role}`")
        st.divider()
        if st.button("Logout", use_container_width=True):
            _logout()
        st.caption("Authenticated session")

    st.markdown(
        '<div class="sva-title">🚗 SVA DIGITAL TWIN</div>'
        '<p class="sva-muted">Zonal Controller-Based Software Vehicle Architecture</p>',
        unsafe_allow_html=True,
    )
    st.divider()

    st.subheader("Central Vehicle Computer")
    cvc, can, ecus, clock = st.columns(4)
    with cvc:
        _metric_card("ESP32 Gateway", "CONNECTED")
    with can:
        _metric_card("CAN Network", "HEALTHY")
    with ecus:
        _metric_card("Active ECUs", "3 / 3")
    with clock:
        _metric_card("Session", role)

    st.divider()
    st.subheader("Live Vehicle Model")
    front, cabin, rear = st.columns(3)
    with front:
        st.markdown('<div class="sva-card">', unsafe_allow_html=True)
        st.markdown('<h3 class="online">FRONT ZONAL ECU — ONLINE</h3>', unsafe_allow_html=True)
        st.caption("CAN Heartbeat 0x101  •  Telemetry 0x102")
        st.metric("Vehicle Speed", "45 km/h")
        st.metric("Steering Angle", "0°")
        st.write("Obstacle: CLEAR")
        st.markdown("</div>", unsafe_allow_html=True)
    with cabin:
        st.markdown('<div class="sva-card">', unsafe_allow_html=True)
        st.markdown('<h3 class="online">CABIN ZONAL ECU — ONLINE</h3>', unsafe_allow_html=True)
        st.caption("CAN Heartbeat 0x201  •  Telemetry 0x202")
        st.metric("Temperature", "26 °C")
        st.write("Driver: DETECTED")
        st.write("Doors: CLOSED  •  Seat belts: WORN")
        st.markdown("</div>", unsafe_allow_html=True)
    with rear:
        st.markdown('<div class="sva-card">', unsafe_allow_html=True)
        st.markdown('<h3 class="online">REAR ZONAL ECU — ONLINE</h3>', unsafe_allow_html=True)
        st.caption("CAN Heartbeat 0x301  •  Telemetry 0x302")
        st.write("Obstacle: CLEAR")
        st.write("Parking Brake: ACTIVE")
        st.write("Rear Camera: NO SIGNAL")
        st.markdown("</div>", unsafe_allow_html=True)

    st.divider()
    st.subheader("CVC Engineering Intelligence")
    diag, recovery, ml, ota = st.columns(4)
    with diag:
        st.info("🔍 Diagnostics\n\nNo active DTCs")
    with recovery:
        st.info("🔧 Self-Healing\n\nRecovery System Ready")
    with ml:
        st.info("🧠 Predictive Maintenance\n\nCondition: NORMAL\nRisk: LOW")
    with ota:
        st.info("📡 OTA Update\n\nFirmware System Ready")

    if role in {"ADMIN", "ENGINEER"}:
        st.divider()
        st.subheader("Engineering Controls")
        if role == "ENGINEER":
            st.warning("Simulation controls are enabled for ENGINEER testing.")
        else:
            st.warning("Administrative controls are enabled.")
        action = st.selectbox("Action", ["View rear ECU", "Inject rear fault", "Run ML prediction"])
        if st.button("Record action", type="primary"):
            _audit(action.upper().replace(" ", "_"), user_id, role)
            st.success("Action recorded in the audit log.")

    if role == "ADMIN":
        with st.expander("Administrator audit log"):
            with sqlite3.connect(AUDIT_DB) as connection:
                rows = connection.execute(
                    "SELECT event_time,user_id,event,detail FROM access_log "
                    "ORDER BY id DESC LIMIT 100"
                ).fetchall()
            st.dataframe(rows, use_container_width=True, hide_index=True)

    st.divider()
    st.caption("STM32 Front/Cabin/Rear ECUs → CAN Bus → ESP32 Gateway → CVC")


def main() -> None:
    if not st.session_state.get("authenticated"):
        _login()
    else:
        _dashboard()


if __name__ == "__main__":
    main()
