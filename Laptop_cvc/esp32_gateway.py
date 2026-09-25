"""Gateway boundary with simulation, serial bridge, and direct CAN support.

The simulator uses an in-memory CAN bus. Hardware implementations can either
use the ESP32 serial bridge or a direct CAN bus interface (for example,
SocketCAN / linux-can) without changing the CVC protocol.
"""

import json
from collections import deque
from typing import Any, Protocol

try:
    import can
except ImportError:  # pragma: no cover - optional hardware dependency
    can = None

try:
    from .can_protocol import CANFrame
except ImportError:
    from can_protocol import CANFrame


def encode_payload(payload: dict[str, Any]) -> bytes:
    """Serialize a logical CAN payload into raw bytes for direct CAN transport."""

    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def decode_payload(raw_data: bytes) -> dict[str, Any]:
    """Decode raw CAN bytes back into the logical payload dictionary."""

    decoded = json.loads(raw_data.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("Direct CAN payload must decode to a JSON object")
    return decoded


class GatewayTransport(Protocol):
    """Transport contract shared by simulation and the physical ESP32 link."""

    @property
    def connected(self) -> bool: ...

    def send(self, frame: CANFrame) -> None: ...

    def receive(self) -> list[CANFrame]: ...


class SimulatedCANBus:
    def __init__(self) -> None:
        self._frames: deque[CANFrame] = deque()

    def publish(self, frame: CANFrame) -> None:
        self._frames.append(frame)

    def receive_all(self) -> list[CANFrame]:
        frames = list(self._frames)
        self._frames.clear()
        return frames


class SimulatedGatewayTransport:
    def __init__(self, bus: SimulatedCANBus | None = None) -> None:
        self.bus = bus or SimulatedCANBus()
        self.connected = True

    def send(self, frame: CANFrame) -> None:
        if not self.connected:
            raise ConnectionError("ESP32 gateway is disconnected")
        self.bus.publish(frame)

    def receive(self) -> list[CANFrame]:
        if not self.connected:
            return []
        return self.bus.receive_all()


class SerialGatewayTransport:
    """Newline-delimited JSON transport for an ESP32 USB serial gateway."""

    def __init__(self, port: str, baudrate: int = 115200) -> None:
        try:
            import serial
        except ImportError as exc:
            raise RuntimeError("Install pyserial to use --port hardware mode") from exc
        self._serial = serial.Serial(port=port, baudrate=baudrate, timeout=0)

    @property
    def connected(self) -> bool:
        return self._serial.is_open

    def send(self, frame: CANFrame) -> None:
        if not self.connected:
            raise ConnectionError("ESP32 serial gateway is disconnected")
        self._serial.write((frame.to_wire() + "\n").encode("utf-8"))

    def receive(self) -> list[CANFrame]:
        frames: list[CANFrame] = []
        while self._serial.in_waiting:
            line = self._serial.readline().decode("utf-8").strip()
            if line:
                frames.append(CANFrame.from_wire(line))
        return frames

    def close(self) -> None:
        self._serial.close()


class DirectCANTransport:
    """Direct physical CAN adapter using python-can.

    The frame payload is serialized to JSON and packed into the CAN payload bytes,
    keeping the logical CVC data model consistent while allowing native CAN bus
    communication without the ESP32 bridge.
    """

    def __init__(
        self,
        channel: str = "can0",
        bustype: str = "socketcan",
        bitrate: int = 500000,
        **kwargs: Any,
    ) -> None:
        if can is None:
            raise RuntimeError("Install python-can to use direct CAN hardware mode")

        self.channel = channel
        self.bustype = bustype
        self.bitrate = bitrate
        self.kwargs = kwargs
        self._bus = can.Bus(
            channel=channel,
            bustype=bustype,
            bitrate=bitrate,
            **kwargs,
        )

    @property
    def connected(self) -> bool:
        return self._bus is not None

    def send(self, frame: CANFrame) -> None:
        if not self.connected:
            raise ConnectionError("Direct CAN bus is disconnected")

        raw_payload = encode_payload(frame.payload)
        if len(raw_payload) > 8:
            raise ValueError(
                "Direct CAN payload exceeds 8 bytes. Use a shorter JSON payload."
            )

        message = can.Message(
            arbitration_id=frame.arbitration_id,
            data=raw_payload,
            is_extended_id=False,
        )
        self._bus.send(message)

    def receive(self) -> list[CANFrame]:
        frames: list[CANFrame] = []
        while True:
            try:
                message = self._bus.recv(timeout=0)
            except can.CanError:
                break

            if message is None:
                break

            if not message.data:
                continue

            payload = decode_payload(message.data)
            frames.append(CANFrame(message.arbitration_id, payload))

        return frames

    def close(self) -> None:
        self._bus.shutdown()


class ESP32Gateway:
    def __init__(self, transport: GatewayTransport) -> None:
        self.transport = transport

    @property
    def connected(self) -> bool:
        return self.transport.connected

    def send(self, frame: CANFrame) -> None:
        self.transport.send(frame)

    def receive(self) -> list[CANFrame]:
        return self.transport.receive()
