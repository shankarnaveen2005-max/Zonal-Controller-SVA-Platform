"""Central Vehicle Computer service for the three-zone SVA prototype."""

from dataclasses import dataclass, field
import time
from typing import Any

from can_protocol import CANFrame, frame_zone
from esp32_gateway import ESP32Gateway


# ============================================================
# ZONAL ECU CONFIGURATION
# ============================================================

ZONES = ("FRONT", "CABIN", "REAR")

# Project-specific Diagnostic Trouble Codes
DTC_CODES = {
    "FRONT": "DTC-CAN-101",
    "CABIN": "DTC-CAN-201",
    "REAR": "DTC-CAN-301"
}


# ============================================================
# ZONAL ECU STATE
# ============================================================

@dataclass
class ZoneState:
    status: str = "OFFLINE"
    last_heartbeat: float | None = None
    telemetry: dict[str, Any] = field(default_factory=dict)


# ============================================================
# CENTRAL VEHICLE COMPUTER
# ============================================================

class CentralVehicleComputer:

    def __init__(
        self,
        gateway: ESP32Gateway,
        heartbeat_timeout_s: float = 3.0
    ) -> None:

        self.gateway = gateway
        self.heartbeat_timeout_s = heartbeat_timeout_s

        # Create state storage for all three zonal ECUs
        self.zones = {
            zone: ZoneState()
            for zone in ZONES
        }

        self.last_error: str | None = None


    # ========================================================
    # RECEIVE AND PROCESS CAN DATA
    # ========================================================

    def poll(self, now: float | None = None) -> None:

        now = time.monotonic() if now is None else now

        # Receive CAN frames through ESP32 Gateway
        for frame in self.gateway.receive():
            self._process_frame(frame, now)

        # Check heartbeat timeout
        for state in self.zones.values():

            if (
                state.last_heartbeat is None
                or now - state.last_heartbeat > self.heartbeat_timeout_s
            ):
                state.status = "OFFLINE"


    # ========================================================
    # PROCESS INDIVIDUAL CAN FRAME
    # ========================================================

    def _process_frame(
        self,
        frame: CANFrame,
        now: float
    ) -> None:

        zone = frame_zone(frame.arbitration_id)

        # Reject invalid CAN frames
        if zone is None or frame.payload.get("zone") != zone:

            self.last_error = (
                f"Rejected invalid CAN frame "
                f"0x{frame.arbitration_id:X}"
            )

            return

        state = self.zones[zone]

        # ----------------------------------------------------
        # HEARTBEAT MESSAGE
        # ----------------------------------------------------

        if frame.arbitration_id % 0x100 == 1:

            state.last_heartbeat = now
            state.status = "ONLINE"

        # ----------------------------------------------------
        # TELEMETRY MESSAGE
        # ----------------------------------------------------

        else:

            state.telemetry = {
                key: value
                for key, value in frame.payload.items()
                if key != "zone"
            }


    # ========================================================
    # ESP32 GATEWAY STATUS
    # ========================================================

    @property
    def gateway_status(self) -> str:

        if self.gateway.connected:
            return "CONNECTED"

        return "DISCONNECTED"


    # ========================================================
    # OVERALL VEHICLE NETWORK STATUS
    # ========================================================

    @property
    def network_status(self) -> str:

        all_ecus_online = all(
            state.status == "ONLINE"
            for state in self.zones.values()
        )

        if self.gateway.connected and all_ecus_online:
            return "HEALTHY"

        return "FAULT DETECTED"


    # ========================================================
    # INTELLIGENT DIAGNOSTICS
    # ========================================================

    def diagnostics(self) -> list[str]:

        faults = []

        # Check individual zonal ECU communication
        for zone in ZONES:

            if self.zones[zone].status != "ONLINE":

                faults.append(
                    f"{DTC_CODES[zone]}: "
                    f"{zone.title()} Zonal ECU communication lost"
                )

        # Check ESP32 Gateway
        if not self.gateway.connected:

            faults.append(
                "DTC-GW-001: "
                "ESP32 Gateway communication lost"
            )

        # Check invalid CAN messages
        if self.last_error:

            faults.append(
                f"DTC-CAN-000: {self.last_error}"
            )

        return faults