"""Shared vehicle-state normalization and optional MQTT publishing."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any


def _camera_state(rear: dict[str, Any]) -> dict[str, Any]:
    return {
        "available": bool(rear.get("camera_available", False)),
        "status": str(rear.get("camera_status", "OFFLINE")),
        "signal": str(rear.get("camera_signal", "NO SIGNAL")),
        "location": str(rear.get("camera_location", "REAR")),
        "stream_url": str(rear.get("camera_stream_url", "")),
    }


def snapshot_from_cvc(
    cvc: Any,
    v2x_alerts: list[Any] | None = None,
) -> dict[str, Any]:
    """Convert CVC zone state into the web/dashboard payload contract."""
    front = cvc.zones["FRONT"].telemetry
    cabin = cvc.zones["CABIN"].telemetry
    rear = cvc.zones["REAR"].telemetry
    alerts = [
        {
            "message_type": getattr(alert, "message_type", "ALERT"),
            "station_id": getattr(alert, "station_id", "unknown"),
            "timestamp": getattr(alert, "timestamp", ""),
            "payload": getattr(alert, "payload", {}),
        }
        for alert in (v2x_alerts or [])
    ]
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "front": {
            "status": cvc.zones["FRONT"].status,
            "speed": front.get("speed", 0.0),
            "steering": front.get("steering", 0.0),
            "obstacle_distance": front.get("obstacle_distance", 0.0),
            "obstacle_status": front.get("obstacle_status", "UNKNOWN"),
        },
        "cabin": {
            "status": cvc.zones["CABIN"].status,
            "temperature": cabin.get("temperature", 0.0),
            "driver_detected": cabin.get("driver_detected", False),
            "doors": cabin.get("doors", {}),
            "seatbelts": cabin.get("seatbelts", {}),
        },
        "rear": {
            "status": cvc.zones["REAR"].status,
            "obstacle_distance": rear.get("obstacle_distance", 0.0),
            "obstacle_status": rear.get("obstacle_status", "UNKNOWN"),
            "parking_brake": rear.get("parking_brake", "UNKNOWN"),
            "rear_light": rear.get("rear_light", "UNKNOWN"),
            "wheel_rpm": rear.get("wheel_rpm", 0),
        },
        "camera": _camera_state(rear),
        "v2x": {
            "status": "ALERT" if alerts else "CLEAR",
            "alerts": alerts[-20:],
        },
    }


class MqttStatePublisher:
    """Optional CVC publisher; disabled unless SVA_MQTT_HOST is configured."""

    def __init__(self) -> None:
        self._client: Any = None
        self.topic = os.getenv("SVA_MQTT_TOPIC", "sva/vehicle/state")
        host = os.getenv("SVA_MQTT_HOST")
        if not host:
            return
        try:
            import paho.mqtt.client as mqtt
            self._client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2,
                client_id=os.getenv("SVA_MQTT_CLIENT_ID", "sva-cvc"),
            )
            username = os.getenv("SVA_MQTT_USERNAME")
            if username:
                self._client.username_pw_set(
                    username,
                    os.getenv("SVA_MQTT_PASSWORD", ""),
                )
            if os.getenv("SVA_MQTT_TLS", "true").lower() == "true":
                self._client.tls_set()
            self._client.connect(
                host,
                int(os.getenv("SVA_MQTT_PORT", "8883")),
                keepalive=30,
            )
            self._client.loop_start()
        except (ImportError, OSError, ValueError):
            self._client = None

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def publish(self, snapshot: dict[str, Any]) -> None:
        if self._client is not None:
            self._client.publish(
                self.topic,
                json.dumps(snapshot, separators=(",", ":")),
                qos=1,
            )

    def close(self) -> None:
        if self._client is not None:
            self._client.loop_stop()
            self._client.disconnect()
