"""Simulation of one STM32 zonal ECU."""

from dataclasses import dataclass
from typing import Any

from can_protocol import CANFrame, message_id


@dataclass
class ZonalECU:
    zone: str
    online: bool = True
    door_state: str = "CLOSED"
    belt_state: str = "WORN"

    # ========================================================
    # HEARTBEAT
    # ========================================================

    def heartbeat(self, timestamp: float) -> CANFrame | None:

        if not self.online:
            return None

        return CANFrame(
            message_id(self.zone, "HEARTBEAT"),
            {
                "zone": self.zone,
                "uptime_s": round(timestamp, 2),
            },
        )


    # ========================================================
    # TELEMETRY
    # ========================================================

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

                "doors": {
                    "front_left": self.door_state,
                    "front_right": self.door_state,
                    "rear_left": self.door_state,
                    "rear_right": self.door_state,
                },

                "seatbelts": {
                    "driver": self.belt_state,
                    "front_passenger": self.belt_state,
                    "rear_left": self.belt_state,
                    "rear_right": self.belt_state,
                },
            },

            "REAR": {
                "obstacle": "CLEAR",
                "parking_brake": True,
                "status": "OK",
            },
        }

        return CANFrame(
            message_id(self.zone, "TELEMETRY"),
            {
                "zone": self.zone,
                "timestamp": round(timestamp, 2),
                **values[self.zone],
            },
        )


    # ========================================================
    # RECEIVE CVC CONTROL COMMAND
    # ========================================================

    def process_command(self, frame: CANFrame) -> bool:
        """Process a control command received from the CVC."""

        if frame.arbitration_id != message_id(
            self.zone,
            "RECOVERY"
        ):
            return False

        if frame.payload.get("zone") != self.zone:
            return False

        if frame.payload.get("command") != "RECOVER":
            return False

        self.recover()

        return True


    # ========================================================
    # SELF-HEALING ACTION
    # ========================================================

    def recover(self) -> None:
        """Simulate recovery of the STM32 zonal ECU."""

        self.online = True