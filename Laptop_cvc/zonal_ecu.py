"""Simulation of one STM32 zonal ECU."""

from dataclasses import dataclass
from typing import Any

from can_protocol import CANFrame, message_id


@dataclass
class ZonalECU:
    zone: str
    online: bool = True

    def heartbeat(self, timestamp: float) -> CANFrame | None:
        if not self.online:
            return None
        return CANFrame(
            message_id(self.zone, "HEARTBEAT"),
            {"zone": self.zone, "uptime_s": round(timestamp, 2)},
        )

    def telemetry(self, timestamp: float) -> CANFrame | None:
        if not self.online:
            return None
        values: dict[str, Any] = {
            "FRONT": {
                "speed_kph": 45,
                "obstacle": "CLEAR",
                "steering_angle_deg": 0,
            },
            "CABIN": {
                "temperature_c": 26,
                "driver_detected": True,
                "seatbelt_fastened": True,
            },
            "REAR": {
                "obstacle": "CLEAR",
                "parking_brake": True,
                "status": "OK",
            },
        }
        return CANFrame(
            message_id(self.zone, "TELEMETRY"),
            {"zone": self.zone, "timestamp": round(timestamp, 2), **values[self.zone]},
        )
