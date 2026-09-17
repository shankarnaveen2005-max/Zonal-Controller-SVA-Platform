"""Central Vehicle Computer service for the three-zone SVA prototype."""

from dataclasses import dataclass, field
import time
from typing import Any

from can_protocol import (
    CANFrame,
    frame_zone,
    message_id,
    recovery_frame,
)
from esp32_gateway import ESP32Gateway


# ============================================================
# ZONAL ECU CONFIGURATION
# ============================================================

ZONES = ("FRONT", "CABIN", "REAR")

DTC_CODES = {
    "FRONT": "DTC-CAN-101",
    "CABIN": "DTC-CAN-201",
    "REAR": "DTC-CAN-301",
}


# ============================================================
# ZONAL ECU STATE
# ============================================================

@dataclass
class ZoneState:
    status: str = "OFFLINE"
    last_heartbeat: float | None = None
    telemetry: dict[str, Any] = field(default_factory=dict)

    # Self-healing information
    recovery_status: str = "IDLE"
    recovery_attempts: int = 0


# ============================================================
# CENTRAL VEHICLE COMPUTER
# ============================================================

class CentralVehicleComputer:

    def __init__(
        self,
        gateway: ESP32Gateway,
        heartbeat_timeout_s: float = 3.0,
    ) -> None:

        self.gateway = gateway
        self.heartbeat_timeout_s = heartbeat_timeout_s

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

        for frame in self.gateway.receive():
            self._process_frame(frame, now)

        for zone, state in self.zones.items():

            if (
                state.last_heartbeat is None
                or now - state.last_heartbeat > self.heartbeat_timeout_s
            ):
                state.status = "OFFLINE"


    # ========================================================
    # PROCESS CAN FRAME
    # ========================================================

    def _process_frame(
        self,
        frame: CANFrame,
        now: float,
    ) -> None:

        zone = frame_zone(frame.arbitration_id)

        if zone is None or frame.payload.get("zone") != zone:

            self.last_error = (
                f"Rejected invalid CAN frame "
                f"0x{frame.arbitration_id:X}"
            )

            return

        state = self.zones[zone]

        # HEARTBEAT
        if frame.arbitration_id == message_id(zone, "HEARTBEAT"):

            state.last_heartbeat = now
            state.status = "ONLINE"

            # Verify successful recovery
            if state.recovery_status in (
                "REQUESTED",
                "WAITING"
            ):
                state.recovery_status = "RECOVERED"

        # TELEMETRY
        elif frame.arbitration_id == message_id(
            zone,
            "TELEMETRY"
        ):

            state.telemetry = {
                key: value
                for key, value in frame.payload.items()
                if key != "zone"
            }

        # RECOVERY
        elif frame.arbitration_id == message_id(
            zone,
            "RECOVERY"
        ):
            pass


    # ========================================================
    # SELF-HEALING / AUTONOMOUS RECOVERY
    # ========================================================

    def request_recovery(self, zone: str) -> None:

        if zone not in self.zones:
            raise ValueError(
                f"Unknown zonal ECU: {zone}"
            )

        state = self.zones[zone]

        if state.status == "ONLINE":
            return

        if not self.gateway.connected:
            state.recovery_status = "FAILED"
            return

        state.recovery_attempts += 1
        state.recovery_status = "REQUESTED"

        frame = recovery_frame(zone)

        self.gateway.send(frame)

        state.recovery_status = "WAITING"


    # ========================================================
    # ESP32 GATEWAY STATUS
    # ========================================================

    @property
    def gateway_status(self) -> str:

        if self.gateway.connected:
            return "CONNECTED"

        return "DISCONNECTED"


    # ========================================================
    # NETWORK STATUS
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

        for zone in ZONES:

            if self.zones[zone].status != "ONLINE":

                faults.append(
                    f"{DTC_CODES[zone]}: "
                    f"{zone.title()} Zonal ECU communication lost"
                )

        if not self.gateway.connected:

            faults.append(
                "DTC-GW-001: "
                "ESP32 Gateway communication lost"
            )

        if self.last_error:

            faults.append(
                f"DTC-CAN-000: {self.last_error}"
            )

        return faults
    