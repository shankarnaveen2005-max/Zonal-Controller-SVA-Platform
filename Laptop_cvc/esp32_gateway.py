"""ESP32 gateway boundary.

The simulator uses an in-memory CAN bus. A hardware implementation can replace
``send``/``receive`` with SocketCAN, USB-CAN, or a pyserial transport without
changing the CVC protocol.
"""

from collections import deque
from typing import Protocol

from can_protocol import CANFrame


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
