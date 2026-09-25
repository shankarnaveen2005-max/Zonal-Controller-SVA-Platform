"""Optional V2X application service for vehicle awareness and safety alerts.

This module provides an MQTT application adapter for development and gateway
integration. It is not a replacement for a certified C-V2X or DSRC modem.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from queue import Empty, Queue
from typing import Any


@dataclass(frozen=True)
class V2XMessage:
    message_type: str
    station_id: str
    timestamp: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "message_type": self.message_type,
            "station_id": self.station_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }

    @classmethod
    def from_bytes(cls, raw_message: bytes) -> "V2XMessage":
        data = json.loads(raw_message.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("V2X message must be a JSON object")

        message_type = data.get("message_type")
        station_id = data.get("station_id")
        timestamp = data.get("timestamp")
        payload = data.get("payload")
        if not all(isinstance(value, str) for value in (message_type, station_id, timestamp)):
            raise ValueError("V2X message metadata is invalid")
        if not isinstance(payload, dict):
            raise ValueError("V2X message payload must be an object")

        return cls(message_type, station_id, timestamp, payload)


class V2XService:
    """Optional MQTT adapter for outbound V2X messages and inbound alerts."""

    def __init__(self) -> None:
        self.vehicle_id = os.getenv("SVA_V2X_STATION_ID", "sva-vehicle-001")
        self.publish_topic = os.getenv("SVA_V2X_PUBLISH_TOPIC", "sva/v2x/out")
        self.subscribe_topic = os.getenv("SVA_V2X_SUBSCRIBE_TOPIC", "sva/v2x/in")
        self._client: Any = None
        self._alerts: Queue[V2XMessage] = Queue()

        host = os.getenv("SVA_V2X_HOST")
        if not host:
            return

        try:
            import paho.mqtt.client as mqtt

            self._client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2,
                client_id=os.getenv("SVA_V2X_CLIENT_ID", f"{self.vehicle_id}-v2x"),
            )
            username = os.getenv("SVA_V2X_USERNAME")
            if username:
                self._client.username_pw_set(
                    username,
                    os.getenv("SVA_V2X_PASSWORD", ""),
                )
            if os.getenv("SVA_V2X_TLS", "true").lower() == "true":
                self._client.tls_set()
            self._client.on_message = self._on_message
            self._client.connect(
                host,
                int(os.getenv("SVA_V2X_PORT", "8883")),
                keepalive=30,
            )
            self._client.subscribe(self.subscribe_topic, qos=1)
            self._client.loop_start()
        except (ImportError, OSError, ValueError):
            self._client = None

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def publish_basic_safety_message(self, snapshot: dict[str, Any]) -> None:
        """Publish current CVC state as an application-level V2X BSM."""
        if self._client is None:
            return

        message = V2XMessage(
            message_type="BSM",
            station_id=self.vehicle_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            payload={
                "vehicle_status": {
                    "front": snapshot.get("front", {}),
                    "rear": snapshot.get("rear", {}),
                },
                "cabin_status": snapshot.get("cabin", {}),
            },
        )
        self._client.publish(
            self.publish_topic,
            json.dumps(message.to_dict(), separators=(",", ":")),
            qos=1,
        )

    def receive_alerts(self) -> list[V2XMessage]:
        alerts: list[V2XMessage] = []
        while True:
            try:
                alerts.append(self._alerts.get_nowait())
            except Empty:
                return alerts

    def _on_message(self, _client: Any, _userdata: Any, message: Any) -> None:
        try:
            self._alerts.put(V2XMessage.from_bytes(message.payload))
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            return

    def close(self) -> None:
        if self._client is not None:
            self._client.loop_stop()
            self._client.disconnect()
