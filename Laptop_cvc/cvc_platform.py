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

# Project-defined diagnostic trouble codes
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

        # Receive all available CAN frames from ESP32 Gateway
        for frame in self.gateway.receive():
            self._process_frame(frame, now)

        # Check heartbeat timeout for each zonal ECU
        for zone, state in self.zones.items():

            if (
                state.last_heartbeat is None
                or now - state.last_heartbeat
                > self.heartbeat_timeout_s
            ):
                state.status = "OFFLINE"


    # ========================================================
    # PROCESS RECEIVED CAN FRAME
    # ========================================================

    def _process_frame(
        self,
        frame: CANFrame,
        now: float,
    ) -> None:

        zone = frame_zone(
            frame.arbitration_id
        )

        # Validate frame
        if (
            zone is None
            or frame.payload.get("zone") != zone
        ):

            self.last_error = (
                f"Rejected invalid CAN frame "
                f"0x{frame.arbitration_id:X}"
            )

            return

        state = self.zones[zone]

        # ====================================================
        # HEARTBEAT MESSAGE
        # ====================================================

        if frame.arbitration_id == message_id(
            zone,
            "HEARTBEAT",
        ):

            state.last_heartbeat = now
            state.status = "ONLINE"

            # Successful heartbeat after recovery request
            # verifies that the zonal ECU has recovered.
            if state.recovery_status in (
                "REQUESTED",
                "WAITING",
            ):

                state.recovery_status = "RECOVERED"

        # ====================================================
        # TELEMETRY MESSAGE
        # ====================================================

        elif frame.arbitration_id == message_id(
            zone,
            "TELEMETRY",
        ):

            state.telemetry = {
                key: value
                for key, value
                in frame.payload.items()
                if key != "zone"
            }

        # ====================================================
        # RECOVERY MESSAGE
        # ====================================================

        elif frame.arbitration_id == message_id(
            zone,
            "RECOVERY",
        ):

            # Recovery commands are handled by the
            # corresponding zonal ECU.
            pass


    # ========================================================
    # SELF-HEALING / AUTONOMOUS RECOVERY
    # ========================================================

    def request_recovery(
        self,
        zone: str,
    ) -> None:

        # Validate zone
        if zone not in self.zones:

            raise ValueError(
                f"Unknown zonal ECU: {zone}"
            )

        state = self.zones[zone]

        # No recovery is required if ECU is already online
        if state.status == "ONLINE":
            return

        # Recovery cannot be transmitted if gateway is down
        if not self.gateway.connected:

            state.recovery_status = "FAILED"
            return

        # Increase recovery attempt counter
        state.recovery_attempts += 1

        state.recovery_status = "REQUESTED"

        # Generate recovery CAN command
        frame = recovery_frame(
            zone
        )

        # Send through ESP32 Gateway
        self.gateway.send(
            frame
        )

        # Wait for heartbeat confirmation
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
    # VEHICLE NETWORK STATUS
    # ========================================================

    @property
    def network_status(self) -> str:

        all_ecus_online = all(
            state.status == "ONLINE"
            for state in self.zones.values()
        )

        if (
            self.gateway.connected
            and all_ecus_online
        ):
            return "HEALTHY"

        return "FAULT DETECTED"


    # ========================================================
    # INTELLIGENT DIAGNOSTICS
    # ========================================================

    def diagnostics(
        self,
    ) -> list[str]:

        faults: list[str] = []

        # ====================================================
        # ZONAL ECU COMMUNICATION DIAGNOSTICS
        # ====================================================

        for zone in ZONES:

            state = self.zones[zone]

            if state.status != "ONLINE":

                faults.append(
                    f"{DTC_CODES[zone]}: "
                    f"{zone.title()} Zonal ECU "
                    f"communication lost"
                )

        # ====================================================
        # ESP32 GATEWAY DIAGNOSTICS
        # ====================================================

        if not self.gateway.connected:

            faults.append(
                "DTC-GW-001: "
                "ESP32 Gateway communication lost"
            )

        # ====================================================
        # CAN MESSAGE VALIDATION ERROR
        # ====================================================

        if self.last_error:

            faults.append(
                f"DTC-CAN-000: "
                f"{self.last_error}"
            )

        return faults

    def vehicle_snapshot(self) -> dict[str, Any]:
        """Return the normalized state shared by desktop and web dashboards."""
        try:
            from live_data import snapshot_from_cvc
        except ImportError:
            from .live_data import snapshot_from_cvc
        return snapshot_from_cvc(self)