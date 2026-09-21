"""Public Streamlit SVA Digital Twin with authentication and audit logging."""



from __future__ import annotations



import hashlib

import hmac

import json

import os

import random

import secrets

import sqlite3

from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
from typing import Any



import streamlit as st





APP_DIR = Path(__file__).resolve().parent

AUDIT_DB = Path(os.getenv("SVA_AUDIT_DB", APP_DIR / "sva_audit.db"))

ROLES = ("ADMIN", "ENGINEER", "VIEWER")



st.set_page_config(

    page_title="SVA Digital Twin",

    page_icon="SVA",

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

        '<div class="sva-title">SVA DIGITAL TWIN</div>'

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





def _vehicle_replica(

    faults: set[str],

    cabin_state: dict[str, dict[str, str]],

) -> str:

    def zone_style(zone: str) -> tuple[str, str, str]:

        if zone in faults:

            return "#713c40", "#ef6262", "OFFLINE"

        return "#244936", "#27c281", "ONLINE"



    front_fill, front_stroke, front_state = zone_style("FRONT")

    cabin_fill, cabin_stroke, cabin_zone_state = zone_style("CABIN")

    rear_fill, rear_stroke, rear_state = zone_style("REAR")



    def state_color(value: str, good: str, bad: str) -> str:

        return good if value in {"CLOSED", "WORN"} else bad



    doors = cabin_state["doors"]

    belts = cabin_state["seatbelts"]

    door_colors = [

        (

            state_color(doors["Front Left"], "#244936", "#713c40"),

            state_color(doors["Front Left"], "#27c281", "#ef6262"),

        ),

        (

            state_color(doors["Front Right"], "#244936", "#713c40"),

            state_color(doors["Front Right"], "#27c281", "#ef6262"),

        ),

        (

            state_color(doors["Rear Left"], "#244936", "#713c40"),

            state_color(doors["Rear Left"], "#27c281", "#ef6262"),

        ),

        (

            state_color(doors["Rear Right"], "#244936", "#713c40"),

            state_color(doors["Rear Right"], "#27c281", "#ef6262"),

        ),

    ]

    belt_colors = [

        state_color(belts[name], "#27c281", "#ef6262")

        for name in ("Driver", "Front Passenger", "Rear Left", "Rear Right")

    ]



    return dedent("""

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

        <g stroke-width="3">

          <rect x="119" y="52" width="182" height="58" rx="8"

                fill="{front_fill}" stroke="{front_stroke}" opacity=".88"/>

          <rect x="114" y="122" width="192" height="236" rx="8"

                fill="{cabin_fill}" stroke="{cabin_stroke}" opacity=".18"/>

          <rect x="119" y="370" width="182" height="74" rx="8"

                fill="{rear_fill}" stroke="{rear_stroke}" opacity=".88"/>

        </g>

        <g stroke-width="2">

          <rect x="117" y="145" width="10" height="74" fill="{door0_fill}" stroke="{door0_stroke}"/>

          <rect x="293" y="145" width="10" height="74" fill="{door1_fill}" stroke="{door1_stroke}"/>

          <rect x="117" y="250" width="10" height="74" fill="{door2_fill}" stroke="{door2_stroke}"/>

          <rect x="293" y="250" width="10" height="74" fill="{door3_fill}" stroke="{door3_stroke}"/>

        </g>

        <g fill="#344b59" stroke="#b3c5cc" stroke-width="2">

          <rect x="145" y="148" width="55" height="65" rx="7"/><rect x="220" y="148" width="55" height="65" rx="7"/>

          <rect x="145" y="252" width="55" height="65" rx="7"/><rect x="220" y="252" width="55" height="65" rx="7"/>

        </g>

        <g stroke-width="5"><line x1="155" y1="158" x2="190" y2="203" stroke="{belt0}"/>

          <line x1="230" y1="158" x2="265" y2="203" stroke="{belt1}"/>

          <line x1="155" y1="262" x2="190" y2="307" stroke="{belt2}"/>

          <line x1="230" y1="262" x2="265" y2="307" stroke="{belt3}"/></g>

        <g class="zone-caption" text-anchor="middle">

          <text x="210" y="79">FRONT ZONAL ECU • {front_state}</text>

          <text x="210" y="178">CABIN • 4 SEATS • {cabin_state}</text>

          <text x="210" y="414">REAR ZONAL ECU • {rear_state}</text>

        </g>

        <g class="can-caption" text-anchor="middle">

          <text x="210" y="98">0x101 / 0x102</text>

          <text x="210" y="196">0x201 / 0x202</text>

          <text x="210" y="432">0x301 / 0x302</text>

        </g>

      </svg>

    </div>

    """).format(

        front_fill=front_fill,

        front_stroke=front_stroke,

        front_state=front_state,

        cabin_fill=cabin_fill,

        cabin_stroke=cabin_stroke,

        cabin_state=cabin_zone_state,

        rear_fill=rear_fill,

        rear_stroke=rear_stroke,

        rear_state=rear_state,

        door0_fill=door_colors[0][0],

        door0_stroke=door_colors[0][1],

        door1_fill=door_colors[1][0],

        door1_stroke=door_colors[1][1],

        door2_fill=door_colors[2][0],

        door2_stroke=door_colors[2][1],

        door3_fill=door_colors[3][0],

        door3_stroke=door_colors[3][1],

        belt0=belt_colors[0],

        belt1=belt_colors[1],

        belt2=belt_colors[2],

        belt3=belt_colors[3],
    ).strip()





def _rear_camera_panel(camera: dict[str, Any]) -> str:

    if camera.get("available"):
        signal_text = "LIVE STREAM READY"
        note = "Camera connected"
    else:
        signal_text = camera.get("signal", "NO SIGNAL")
        note = "Camera Not Connected"

    return dedent("""

    <div class="model-shell">

      <div class="sva-muted"><b>REAR CAMERA</b></div>

      <div class="camera-screen">

        <div class="signal">{signal_text}</div>

        <div>{note}</div>

      </div>

      <div class="camera-meta">Status : {status}

        Signal : {signal}

        Location: {location}</div>

      <div class="sva-muted">Reserved for the future ESP32 camera stream</div>

    </div>

    """).format(
        status=camera.get("status", "OFFLINE"),
        signal=camera.get("signal", "NO SIGNAL"),
        location=camera.get("location", "REAR"),
        signal_text=signal_text,
        note=note,
    ).strip()





def _metric_card(label: str, value: str, state: str = "online") -> None:

    st.markdown(

        f'<div class="sva-card"><div class="sva-muted">{label}</div>'

        f'<h3 class="{state}">{value}</h3></div>',

        unsafe_allow_html=True,

    )





def _faults() -> set[str]:

    return st.session_state.setdefault("web_faults", set())





def _cabin_state() -> dict[str, dict[str, str]]:

    return st.session_state.setdefault(

        "web_cabin_state",

        {

            "doors": {

                "Front Left": "CLOSED",

                "Front Right": "CLOSED",

                "Rear Left": "CLOSED",

                "Rear Right": "CLOSED",

            },

            "seatbelts": {

                "Driver": "WORN",

                "Front Passenger": "WORN",

                "Rear Left": "WORN",

                "Rear Right": "WORN",

            },

        },

    )




def _vehicle_state() -> dict[str, Any]:
    """Single hardware-ready state consumed by the web UI.

    Today it is fed by simulation. Later an MQTT/CVC adapter can update the
    same dictionary without changing the dashboard.
    """
    cabin = _cabin_state()
    return st.session_state.setdefault(
        "vehicle_state",
        {
            "source": "SIMULATION",
            "front": {"speed": 45.0, "steering": 0.0, "obstacle_distance": 35.0, "obstacle_status": "CLEAR"},
            "cabin": {"temperature": 26.0, "driver_detected": True, "doors": cabin["doors"], "seatbelts": cabin["seatbelts"]},
            "rear": {"obstacle_distance": 30.0, "obstacle_status": "CLEAR", "parking_brake": "ACTIVE", "rear_light": "OFF", "wheel_rpm": 0},
            "camera": {"available": False, "status": "OFFLINE", "signal": "NO SIGNAL", "location": "REAR"},
            "last_update": datetime.now(timezone.utc).isoformat(),
        },
    )


def _refresh_simulation_state() -> None:
    """Update the shared state while no physical hardware is connected."""
    state = _vehicle_state()
    state["source"] = "SIMULATION"
    if "FRONT" not in _faults():
        state["front"].update(
            speed=round(random.uniform(20, 80), 1),
            steering=round(random.uniform(-30, 30), 1),
        )
        d = round(random.uniform(5, 100), 1)
        state["front"].update(obstacle_distance=d, obstacle_status="WARNING" if d < 15 else "CLEAR")
    if "CABIN" not in _faults():
        state["cabin"]["temperature"] = round(random.uniform(22, 32), 1)
        state["cabin"]["driver_detected"] = random.choice([True, True, True, False])
    if "REAR" not in _faults():
        d = round(random.uniform(5, 100), 1)
        state["rear"].update(
            obstacle_distance=d,
            obstacle_status="WARNING" if d < 15 else "CLEAR",
            parking_brake=random.choice(["ACTIVE", "RELEASED"]),
            rear_light=random.choice(["ON", "OFF"]),
            wheel_rpm=random.randint(0, 1400),
        )
    state["last_update"] = datetime.now(timezone.utc).isoformat()


def _apply_hardware_payload(payload: dict[str, Any]) -> None:
    """Future MQTT/CVC entry point. Merge validated hardware data into shared state."""
    state = _vehicle_state()
    for section in ("front", "cabin", "rear", "camera"):
        incoming = payload.get(section)
        if isinstance(incoming, dict):
            state[section].update(incoming)
    state["source"] = "HARDWARE / MQTT"
    state["last_update"] = datetime.now(timezone.utc).isoformat()




def _dashboard() -> None:

    user_id = st.session_state["user_id"]

    role = st.session_state["role"]

    faults = _faults()

    cabin_state = _cabin_state()

    vehicle_state = _vehicle_state()

    # Keep cabin visualization tied to the shared state.
    vehicle_state["cabin"]["doors"] = cabin_state["doors"]
    vehicle_state["cabin"]["seatbelts"] = cabin_state["seatbelts"]

    gateway_fault = "ESP32_GATEWAY" in faults

    ecu_faults = {"FRONT", "CABIN", "REAR"} & faults

    network_healthy = not faults

    with st.sidebar:

        st.markdown("### SVA DIGITAL TWIN")

        st.markdown(f"**User:** `{user_id}`")

        st.markdown(f"**Role:** `{role}`")

        st.divider()

        if st.button("Logout", use_container_width=True):

            _logout()

        st.caption("Authenticated session")

        st.caption(f"Data source: {vehicle_state['source']}")

        if st.button("Refresh telemetry", use_container_width=True):
            _refresh_simulation_state()
            _audit("TELEMETRY_REFRESH", user_id, vehicle_state["source"])
            st.rerun()



    st.markdown(

        '<div class="sva-title">SVA DIGITAL TWIN</div>'

        '<p class="sva-muted">Zonal Controller-Based Software Vehicle Architecture</p>',

        unsafe_allow_html=True,

    )

    st.divider()

    st.subheader("Central Vehicle Computer")

    cvc, can, ecus, clock = st.columns(4)

    with cvc:

        _metric_card(

            "ESP32 Gateway",

            "OFFLINE" if gateway_fault else "CONNECTED",

            "offline" if gateway_fault else "online",

        )

    with can:

        _metric_card("CAN Network", "FAULT" if not network_healthy else "HEALTHY",

                     "offline" if not network_healthy else "online")

    with ecus:

        _metric_card("Active ECUs", f"{3 - len(ecu_faults)} / 3",

                     "offline" if ecu_faults else "online")

    with clock:

        _metric_card("Session", role)



    st.divider()

    st.subheader("Live Vehicle Model")
    vehicle, camera = st.columns([1.7, 1])
    with vehicle:
        st.html(_vehicle_replica(faults, cabin_state))
    with camera:
        st.html(_rear_camera_panel(vehicle_state["camera"]))



    st.subheader("Zonal ECU Telemetry")

    front, cabin, rear = st.columns(3)

    with front:

        state = "OFFLINE" if "FRONT" in faults else "ONLINE"

        style = "offline" if state == "OFFLINE" else "online"

        st.markdown(f'<h3 class="{style}">FRONT ZONAL ECU — {state}</h3>', unsafe_allow_html=True)

        st.caption("CAN Heartbeat 0x101  •  Telemetry 0x102")

        st.write(f"Speed: **{vehicle_state['front']['speed']} km/h**")

        st.write(f"Steering: **{vehicle_state['front']['steering']}°**")

        st.write(f"Obstacle: **{vehicle_state['front']['obstacle_status']}** ({vehicle_state['front']['obstacle_distance']} m)")

    with cabin:

        state = "OFFLINE" if "CABIN" in faults else "ONLINE"

        style = "offline" if state == "OFFLINE" else "online"

        st.markdown(f'<h3 class="{style}">CABIN ZONAL ECU — {state}</h3>', unsafe_allow_html=True)

        st.caption("CAN Heartbeat 0x201  •  Telemetry 0x202")

        st.write(f"Temperature: **{vehicle_state['cabin']['temperature']} °C**")

        st.write("Driver: **DETECTED**" if vehicle_state["cabin"]["driver_detected"] else "Driver: **NOT DETECTED**")

        doors_closed = sum(value == "CLOSED" for value in cabin_state["doors"].values())

        belts_worn = sum(value == "WORN" for value in cabin_state["seatbelts"].values())

        st.write(f"Doors: **{doors_closed}/4 CLOSED**")

        st.write(f"Seat belts: **{belts_worn}/4 WORN**")

    with rear:

        state = "OFFLINE" if "REAR" in faults else "ONLINE"

        style = "offline" if state == "OFFLINE" else "online"

        st.markdown(f'<h3 class="{style}">REAR ZONAL ECU — {state}</h3>', unsafe_allow_html=True)

        st.caption("CAN Heartbeat 0x301  •  Telemetry 0x302")

        st.write(f"Obstacle: **{vehicle_state['rear']['obstacle_status']}** ({vehicle_state['rear']['obstacle_distance']} m)")

        st.write(f"Parking Brake: **{vehicle_state['rear']['parking_brake']}**")

        st.write(f"Rear light: **{vehicle_state['rear']['rear_light']}**")

        st.write(f"Wheel RPM: **{vehicle_state['rear']['wheel_rpm']}**")



    st.divider()

    st.subheader("Cabin Controls")

    if role == "VIEWER":

        st.info("Door and seat-belt controls require ENGINEER or ADMIN permission.")

    else:

        door_col, belt_col = st.columns(2)

        with door_col:

            st.markdown("**Four-door status**")

            for door, current in cabin_state["doors"].items():

                if st.button(

                    f"{door}: {current}",

                    key=f"web_door_{door}",

                    use_container_width=True,

                ):

                    cabin_state["doors"][door] = (

                        "OPEN" if current == "CLOSED" else "CLOSED"

                    )

                    _audit(

                        "DOOR_STATE_CHANGED",

                        user_id,

                        f"{door} | {cabin_state['doors'][door]}",

                    )

                    st.rerun()

        with belt_col:

            st.markdown("**Four-seat-belt status**")

            for seat, current in cabin_state["seatbelts"].items():

                if st.button(

                    f"{seat}: {current}",

                    key=f"web_belt_{seat}",

                    use_container_width=True,

                ):

                    cabin_state["seatbelts"][seat] = (

                        "NOT WORN" if current == "WORN" else "WORN"

                    )

                    _audit(

                        "SEATBELT_STATE_CHANGED",

                        user_id,

                        f"{seat} | {cabin_state['seatbelts'][seat]}",

                    )

                    st.rerun()

        if st.button("Restore all doors and seat belts", use_container_width=True):

            for door in cabin_state["doors"]:

                cabin_state["doors"][door] = "CLOSED"

            for seat in cabin_state["seatbelts"]:

                cabin_state["seatbelts"][seat] = "WORN"

            _audit("CABIN_SAFETY_STATE_RESTORED", user_id)

            st.rerun()



    st.divider()

    st.subheader("CVC Engineering Intelligence")

    diag, recovery, ml, ota = st.columns(4)

    with diag:

        if faults:

            st.error("🔍 Diagnostics\n\n" + "\n".join(f"DTC-{fault}" for fault in sorted(faults)))

        else:

            st.info("🔍 Diagnostics\n\nNo active DTCs")

    with recovery:

        st.warning("🔧 Self-Healing\n\nRecovery required" if faults else

                   "🔧 Self-Healing\n\nRecovery System Ready")

    with ml:

        st.info("🧠 Predictive Maintenance\n\nCondition: NORMAL\nRisk: LOW")

    with ota:

        st.info("📡 OTA Update\n\nFirmware System Ready")



    st.divider()

    st.subheader("OTA Firmware Update")

    ota_left, ota_right = st.columns([1, 2])

    with ota_left:

        ota_zone = st.selectbox(

            "Target ECU",

            ["FRONT", "CABIN", "REAR"],

            key="web_ota_zone",

            disabled=role == "VIEWER",

        )

        ota_version = st.text_input(

            "Firmware version",

            value="v1.1.0",

            key="web_ota_version",

            disabled=role == "VIEWER",

        )

        ota_requested = st.button(

            "Start OTA update",

            type="primary",

            use_container_width=True,

            disabled=role == "VIEWER",

        )

    with ota_right:

        if role == "VIEWER":

            st.info("OTA updates require ENGINEER or ADMIN permission.")

        elif ota_requested:

            event = "OTA_UPDATE"

            _audit(event, user_id, f"{ota_zone} | {ota_version}")

            st.session_state.web_ota_message = (

                f"{ota_zone} ECU update to {ota_version} completed successfully."

            )

        if st.session_state.get("web_ota_message"):

            st.success(st.session_state.web_ota_message)

        else:

            st.info("Select a target ECU and firmware version to begin.")



    st.divider()

    st.subheader("Fault Injection")

    if role == "VIEWER":

        st.info("Fault injection requires ENGINEER or ADMIN permission.")

    else:

        st.caption("Simulation only — use this to test diagnostics and recovery behavior.")

        fault_cols = st.columns(4)

        fault_targets = (

            ("FRONT", "Front ECU"),

            ("CABIN", "Cabin ECU"),

            ("REAR", "Rear ECU"),

            ("ESP32_GATEWAY", "ESP32 Gateway"),

        )

        for column, (fault_id, label) in zip(fault_cols, fault_targets):

            with column:

                injected = fault_id in faults

                if st.button(

                    f"Clear {label}" if injected else f"Inject {label}",

                    key=f"fault_{fault_id}",

                    use_container_width=True,

                ):

                    if injected:

                        faults.discard(fault_id)

                        action = "FAULT_CLEARED"

                    else:

                        faults.add(fault_id)

                        action = "FAULT_INJECTED"

                    _audit(action, user_id, fault_id)

                    st.rerun()

        if faults and st.button("Clear all faults", use_container_width=True):

            faults.clear()

            _audit("ALL_FAULTS_CLEARED", user_id)

            st.rerun()



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

    st.caption(f"Data source: {vehicle_state['source']}  •  STM32 Front/Cabin/Rear ECUs → CAN Bus → ESP32 Gateway → CVC → MQTT/Cloud → Web Digital Twin")





def main() -> None:

    if not st.session_state.get("authenticated"):

        _login()

    else:

        _dashboard()





if __name__ == "__main__":

    main()
