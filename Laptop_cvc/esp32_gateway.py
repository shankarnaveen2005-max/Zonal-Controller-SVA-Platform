"""ESP32 gateway boundary.

The simulator uses an in-memory CAN bus. A hardware implementation can replace
``send``/``receive`` with SocketCAN, USB-CAN, or a pyserial transport without
changing the CVC protocol.
"""

from collections import deque

from can_protocol import CANFrame


class SimulatedCANBus:
    def __init__(self) -> None:
        self._frames: deque[CANFrame] = deque()

    def publish(self, frame: CANFrame) -> None:
        self._frames.append(frame)

    def receive_all(self) -> list[CANFrame]:
        frames = list(self._frames)
        self._frames.clear()
        return frames


class ESP32Gateway:
    def __init__(self, bus: SimulatedCANBus) -> None:
        self.bus = bus
        self.connected = True

    def send(self, frame: CANFrame) -> None:
        if not self.connected:
            raise ConnectionError("ESP32 gateway is disconnected")
        self.bus.publish(frame)

    def receive(self) -> list[CANFrame]:
        if not self.connected:
            return []
        return self.bus.receive_all()
