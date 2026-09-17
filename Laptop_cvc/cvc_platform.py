"""Central Vehicle Computer service for the three-zone SVA prototype."""

from dataclasses import dataclass, field
import time
from typing import Any

from can_protocol import CANFrame, frame_zone
from esp32_gateway import ESP32Gateway

ZONES = ("FRONT", "CABIN", "REAR")


@dataclass
class ZoneState:
    status: str = "OFFLINE"
    last_heartbeat: float | None = None
    telemetry: dict[str, Any] = field(default_factory=dict)


class CentralVehicleComputer:
    def __init__(self, gateway: ESP32Gateway, heartbeat_timeout_s: float = 3.0) -> None:
        self.gateway = gateway
        self.heartbeat_timeout_s = heartbeat_timeout_s
        self.zones = {zone: ZoneState() for zone in ZONES}
        self.last_error: str | None = None

    def poll(self, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        for frame in self.gateway.receive():
            self._process_frame(frame, now)
        for state in self.zones.values():
            if state.last_heartbeat is None or now - state.last_heartbeat > self.heartbeat_timeout_s:
                state.status = "OFFLINE"

    def _process_frame(self, frame: CANFrame, now: float) -> None:
        zone = frame_zone(frame.arbitration_id)
        if zone is None or frame.payload.get("zone") != zone:
            self.last_error = f"Rejected invalid CAN frame 0x{frame.arbitration_id:X}"
            return
        state = self.zones[zone]
        if frame.arbitration_id % 0x100 == 1:
            state.last_heartbeat = now
            state.status = "ONLINE"
        else:
            state.telemetry = {
                key: value for key, value in frame.payload.items() if key != "zone"
            }

    @property
    def gateway_status(self) -> str:
        return "CONNECTED" if self.gateway.connected else "DISCONNECTED"

    @property
    def network_status(self) -> str:
        return "HEALTHY" if self.gateway.connected and all(
            state.status == "ONLINE" for state in self.zones.values()
        ) else "FAULT DETECTED"

    def diagnostics(self) -> list[str]:
        faults = [
            f"DTC-CAN-{index}01: {zone.title()} zonal ECU communication lost"
            for index, zone in enumerate(ZONES, start=1)
            if self.zones[zone].status != "ONLINE"
        ]
        if not self.gateway.connected:
            faults.append("DTC-GW-001: ESP32 gateway communication lost")
        if self.last_error:
            faults.append(f"DTC-CAN-000: {self.last_error}")
        return faults
