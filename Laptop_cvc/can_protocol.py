"""CAN application protocol shared by zonal ECUs, the gateway, and the CVC."""

from dataclasses import dataclass
import json
from typing import Any


# ============================================================
# CAN IDENTIFIERS
# ============================================================

ZONE_IDS = {
    "FRONT": 0x100,
    "CABIN": 0x200,
    "REAR": 0x300
}

HEARTBEAT_OFFSET = 0x01
TELEMETRY_OFFSET = 0x02
RECOVERY_OFFSET = 0x10


# ============================================================
# CAN FRAME
# ============================================================

@dataclass(frozen=True)
class CANFrame:
    arbitration_id: int
    payload: dict[str, Any]

    def to_wire(self) -> str:
        """Encode one frame as a newline-delimited gateway message."""

        return json.dumps(
            {
                "id": self.arbitration_id,
                "data": self.payload
            },
            separators=(",", ":"),
        )

    @classmethod
    def from_wire(cls, message: str) -> "CANFrame":
        """Decode a gateway message into a CAN frame."""

        data = json.loads(message)

        if (
            not isinstance(data, dict)
            or not isinstance(data.get("id"), int)
        ):
            raise ValueError(
                "CAN frame must contain an integer id"
            )

        payload = data.get("data")

        if not isinstance(payload, dict):
            raise ValueError(
                "CAN frame data must be an object"
            )

        return cls(
            data["id"],
            payload
        )


# ============================================================
# MESSAGE ID GENERATOR
# ============================================================

def message_id(zone: str, message_type: str) -> int:
    """Return the standard 11-bit identifier for a zone message."""

    try:
        base_id = ZONE_IDS[zone]

    except KeyError as exc:
        raise ValueError(
            f"Unknown zone: {zone}"
        ) from exc

    offsets = {
        "HEARTBEAT": HEARTBEAT_OFFSET,
        "TELEMETRY": TELEMETRY_OFFSET,
        "RECOVERY": RECOVERY_OFFSET
    }

    try:
        return base_id + offsets[message_type]

    except KeyError as exc:
        raise ValueError(
            f"Unknown CAN message type: {message_type}"
        ) from exc


# ============================================================
# IDENTIFY ZONE FROM CAN ID
# ============================================================

def frame_zone(arbitration_id: int) -> str | None:
    """Resolve a CAN frame identifier to its zonal controller."""

    for zone, base_id in ZONE_IDS.items():

        valid_ids = (
            base_id + HEARTBEAT_OFFSET,
            base_id + TELEMETRY_OFFSET,
            base_id + RECOVERY_OFFSET
        )

        if arbitration_id in valid_ids:
            return zone

    return None


# ============================================================
# RECOVERY COMMAND
# ============================================================

def recovery_frame(zone: str) -> CANFrame:
    """Create a CVC recovery request for a zonal ECU."""

    return CANFrame(
        arbitration_id=message_id(zone, "RECOVERY"),
        payload={
            "zone": zone,
            "command": "RECOVER"
        }
    )