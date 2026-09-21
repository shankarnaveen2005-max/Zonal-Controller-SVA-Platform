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
    .model-shell { background: #1b2935; border: 1px solid #395361;
      border-radius: 12px; padding: 14px; }
    .camera-screen { min-height: 330px; background: #030609; border: 1px solid #526a75;
      border-radius: 8px; display: flex; flex-direction: column;
      align-items: center; justify-content: center; color: #dbe7eb; }
    .camera-screen .signal { color: #ef6262; font-size: 1.5rem; font-weight: 700; }
    .camera-meta { color: #ef6262; font-family: monospace; font-weight: 700;
      white-space: pre-line; margin-top: 14px; }
    .zone-caption { fill: #e8f1f5; font: 700 15px Arial, sans-serif; }
    .can-caption { fill: #9fc0ce; font: 12px monospace; }
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


def _vehicle_replica() -> str:
    return """
    <div class="model-shell">
      <div class="sva-muted"><b>LIVE VEHICLE MODEL</b></div>
      <svg viewBox="0 0 620 510" width="100%" role="img"
           aria-label="Front cabin rear zonal vehicle model">
        <text x="210" y="22" text-anchor="middle" fill="#b8cbd3"
              font-family="Arial" font-size="12" font-weight="bold">FRONT OF VEHICLE</text>
        <text x="210" y="496" text-anchor="middle" fill="#b8cbd3"
              font-family="Arial" font-size="12" font-weight="bold">REAR OF VEHICLE</text>
        <path d="M130 34 Q105 45 105 78 L105 430 Q105 465 135 480
                 L285 480 Q315 465 315 430 L315 78 Q315 45 290 34 Z"
              fill="#0b1116" stroke="#91aab5" stroke-width="4"/>
        <rect x="130" y="48" width="160" height="72" rx="12"
              fill="#203b4a" stroke="#6dd5fa" stroke-width="2"/>
        <path d="M130 130 L290 130 L296 350 L124 350 Z"
              fill="#182c37" stroke="#557581" stroke-width="2"/>
        <rect x="124" y="366" width="172" height="85"
              fill="#18242b" stroke="#557581" stroke-width="2"/>
        <g fill="#05080a" stroke="#738b95" stroke-width="2">
          <rect x="91" y="104" width="22" height="72" rx="9"/>
          <rect x="299" y="104" width="22" height="72" rx="9"/>
          <rect x="91" y="330" width="22" height="72" rx="9"/>
          <rect x="299" y="330" width="22" height="72" rx="9"/>
        </g>
        <g fill="#f6d36b" stroke="#fff0a8"><rect x="142" y="38" width="25" height="10" rx="4"/>
          <rect x="257" y="38" width="25" height="10" rx="4"/></g>
        <g fill="#e85a5a" stroke="#ff9b9b"><rect x="142" y="451" width="25" height="10" rx="4"/>
          <rect x="257" y="451" width="25" height="10" rx="4"/></g>
        <g fill="#244936" stroke="#27c281" stroke-width="2">
          <rect x="117" y="145" width="10" height="74"/><rect x="293" y="145" width="10" height="74"/>
          <rect x="117" y="250" width="10" height="74"/><rect x="293" y="250" width="10" height="74"/>
        </g>
        <g fill="#344b59" stroke="#b3c5cc" stroke-width="2">
          <rect x="145" y="148" width="55" height="65" rx="7"/><rect x="220" y="148" width="55" height="65" rx="7"/>
          <rect x="145" y="252" width="55" height="65" rx="7"/><rect x="220" y="252" width="55" height="65" rx="7"/>
        </g>
        <g stroke="#27c281" stroke-width="5"><line x1="155" y1="158" x2="190" y2="203"/>
          <line x1="230" y1="158" x2="265" y2="203"/><line x1="155" y1="262" x2="190" y2="307"/>
          <line x1="230" y1="262" x2="265" y2="307"/></g>
        <g class="zone-caption" text-anchor="middle">
          <text x="210" y="79">FRONT ZONAL ECU</text>
          <text x="210" y="178">CABIN • 4 SEATS</text>
          <text x="210" y="414">REAR ZONAL ECU</text>
        </g>
        <g class="can-caption" text-anchor="middle">
          <text x="210" y="98">0x101 / 0x102</text>
          <text x="210" y="196">0x201 / 0x202</text>
          <text x="210" y="432">0x301 / 0x302</text>
        </g>
      </svg>
    </div>
    """


def _rear_camera_panel() -> str:
    return """
    <div class="model-shell">
      <div class="sva-muted"><b>REAR CAMERA</b></div>
      <div class="camera-screen">
        <div class="signal">NO SIGNAL</div>
        <div>Camera Not Connected</div>
      </div>
      <div class="camera-meta">Status : OFFLINE
Signal : NO SIGNAL
Location: REAR</div>
      <div class="sva-muted">Reserved for the future ESP32 camera stream</div>
    </div>
    """


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
    vehicle, camera = st.columns([1.7, 1])
    with vehicle:
        st.markdown(_vehicle_replica(), unsafe_allow_html=True)
    with camera:
        st.markdown(_rear_camera_panel(), unsafe_allow_html=True)

    st.subheader("Zonal ECU Telemetry")
    front, cabin, rear = st.columns(3)
    with front:
        st.markdown('<div class="sva-card">', unsafe_allow_html=True)
        st.markdown('<h3 class="online">FRONT ZONAL ECU — ONLINE</h3>', unsafe_allow_html=True)
        st.caption("CAN Heartbeat 0x101  •  Telemetry 0x102")
        st.write("Speed: **45 km/h**")
        st.write("Steering: **0°**")
        st.write("Obstacle: CLEAR")
        st.markdown("</div>", unsafe_allow_html=True)
    with cabin:
        st.markdown('<div class="sva-card">', unsafe_allow_html=True)
        st.markdown('<h3 class="online">CABIN ZONAL ECU — ONLINE</h3>', unsafe_allow_html=True)
        st.caption("CAN Heartbeat 0x201  •  Telemetry 0x202")
        st.write("Temperature: **26 °C**")
        st.write("Driver: DETECTED")
        st.write("Doors: CLOSED  •  Seat belts: WORN")
        st.markdown("</div>", unsafe_allow_html=True)
    with rear:
        st.markdown('<div class="sva-card">', unsafe_allow_html=True)
        st.markdown('<h3 class="online">REAR ZONAL ECU — ONLINE</h3>', unsafe_allow_html=True)
        st.caption("CAN Heartbeat 0x301  •  Telemetry 0x302")
        st.write("Obstacle: CLEAR")
        st.write("Parking Brake: ACTIVE")
        st.write("Rear light: **OFF**")
        st.write("Wheel RPM: **0**")
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
