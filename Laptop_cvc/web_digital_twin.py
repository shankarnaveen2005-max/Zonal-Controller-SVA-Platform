import streamlit as st
from datetime import datetime

# ---------------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------------

st.set_page_config(
    page_title="SVA Digital Twin",
    page_icon="🚗",
    layout="wide",
)

# ---------------------------------------------------------
# TITLE
# ---------------------------------------------------------

st.title("🚗 SVA Digital Twin")
st.caption(
    "Zonal Controller-Based Software Vehicle Architecture Platform"
)

st.divider()

# ---------------------------------------------------------
# SYSTEM STATUS
# ---------------------------------------------------------

st.subheader("Central Vehicle Computer")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("ESP32 Gateway", "CONNECTED")

with col2:
    st.metric("CAN Network", "HEALTHY")

with col3:
    st.metric("Active ECUs", "3 / 3")

with col4:
    st.metric(
        "System Time",
        datetime.now().strftime("%H:%M:%S"),
    )

st.divider()

# ---------------------------------------------------------
# ZONAL ECU STATUS
# ---------------------------------------------------------

st.subheader("Zonal ECU Network")

front, cabin, rear = st.columns(3)

with front:
    st.success("FRONT ZONAL ECU — ONLINE")

    st.write("**CAN Heartbeat:** 0x101")
    st.write("**CAN Telemetry:** 0x102")

    st.metric("Vehicle Speed", "45 km/h")
    st.metric("Steering Angle", "0°")

    st.write("Front Obstacle: CLEAR")


with cabin:
    st.success("CABIN ZONAL ECU — ONLINE")

    st.write("**CAN Heartbeat:** 0x201")
    st.write("**CAN Telemetry:** 0x202")

    st.metric("Cabin Temperature", "26 °C")

    st.write("Driver: DETECTED")
    st.write("Doors: CLOSED")
    st.write("Seat Belts: WORN")


with rear:
    st.success("REAR ZONAL ECU — ONLINE")

    st.write("**CAN Heartbeat:** 0x301")
    st.write("**CAN Telemetry:** 0x302")

    st.write("Rear Obstacle: CLEAR")
    st.write("Parking Brake: ACTIVE")
    st.write("Rear System: OK")

st.divider()

# ---------------------------------------------------------
# CVC FUNCTIONS
# ---------------------------------------------------------

st.subheader("CVC Engineering Intelligence")

diag, recovery, ml, ota = st.columns(4)

with diag:
    st.info("🔍 Diagnostics")
    st.write("No active DTCs")

with recovery:
    st.info("🔧 Self-Healing")
    st.write("Recovery System Ready")

with ml:
    st.info("🧠 Predictive Maintenance")
    st.write("Vehicle Condition: NORMAL")
    st.write("Risk Level: LOW")

with ota:
    st.info("📡 OTA Update")
    st.write("Firmware System Ready")

st.divider()

# ---------------------------------------------------------
# VEHICLE NETWORK ARCHITECTURE
# ---------------------------------------------------------

st.subheader("Vehicle Network Architecture")

st.code(
    """
FRONT ZONAL ECU ──┐
CABIN ZONAL ECU ──┼── CAN BUS ──► ESP32 GATEWAY ──► CVC
REAR ZONAL ECU ───┘
                                            │
                                            ▼
                              SVA DIGITAL TWIN
    """,
    language=None,
)

st.caption(
    "Development of a Zonal Controller-Based "
    "Software Vehicle Architecture (SVA) Platform"
)