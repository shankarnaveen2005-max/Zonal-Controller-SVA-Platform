"""OpenCV rear-camera pedestrian detection and optional V2X alerts."""

from __future__ import annotations

import argparse
import threading
import time
from datetime import datetime, timezone
from typing import Any

import cv2

try:
    from .v2x import V2XService
except ImportError:
    from v2x import V2XService


class CameraMonitorState:
    """Thread-safe camera health and detection state for dashboard telemetry."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._available = False
        self._status = "OFFLINE"
        self._signal = "NO SIGNAL"
        self._detection_status = "UNAVAILABLE"
        self._hazard: dict[str, Any] | None = None
        self._last_frame_at: str | None = None
        self._error: str | None = None

    def set_active(self) -> None:
        with self._lock:
            self._available = True
            self._status = "ACTIVE"
            self._signal = "CONNECTED"
            self._detection_status = "CLEAR"
            self._hazard = None
            self._error = None

    def record_frame(self, hazard: dict[str, Any] | None) -> None:
        with self._lock:
            self._last_frame_at = datetime.now(timezone.utc).isoformat()
            self._detection_status = (
                "PEDESTRIAN IN REAR PATH" if hazard else "CLEAR"
            )
            self._hazard = dict(hazard) if hazard else None

    def set_error(self, message: str) -> None:
        with self._lock:
            self._available = False
            self._status = "ERROR"
            self._signal = "NO SIGNAL"
            self._detection_status = "UNAVAILABLE"
            self._hazard = None
            self._error = message

    def set_stopped(self) -> None:
        with self._lock:
            if self._status == "ERROR":
                return
            self._available = False
            self._status = "OFFLINE"
            self._signal = "NO SIGNAL"
            self._detection_status = "UNAVAILABLE"
            self._hazard = None

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "available": self._available,
                "status": self._status,
                "signal": self._signal,
                "location": "REAR",
                "stream_url": "",
                "detection_status": self._detection_status,
                "hazard": dict(self._hazard) if self._hazard else None,
                "last_frame_at": self._last_frame_at,
                "error": self._error,
            }


class RearCameraDetector:
    """Detect pedestrians approaching the center of the rear-camera view."""

    def __init__(
        self,
        confirmation_frames: int = 2,
        hog_detector: Any | None = None,
    ) -> None:
        self._hog = hog_detector or cv2.HOGDescriptor()
        if hog_detector is None:
            self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        self._confirmation_frames = max(1, confirmation_frames)
        self._hazard_streak = 0

    def process_frame(
        self,
        frame: Any,
    ) -> tuple[Any, dict[str, Any] | None]:
        height, width = frame.shape[:2]
        boxes, _weights = self._hog.detectMultiScale(
            frame,
            winStride=(8, 8),
            padding=(8, 8),
            scale=1.05,
        )
        qualifying_boxes = []

        for x, y, box_width, box_height in boxes:
            center_x = x + box_width / 2
            box_bottom = y + box_height
            in_rear_path = (
                width * 0.2 <= center_x <= width * 0.8
                and box_bottom >= height * 0.68
                and box_height >= height * 0.12
            )
            color = (0, 0, 255) if in_rear_path else (0, 200, 255)
            cv2.rectangle(
                frame,
                (x, y),
                (x + box_width, y + box_height),
                color,
                2,
            )
            if in_rear_path:
                qualifying_boxes.append((x, y, box_width, box_height))

        zone_top = int(height * 0.68)
        cv2.line(frame, (int(width * 0.2), zone_top),
                 (int(width * 0.8), zone_top), (0, 180, 255), 2)

        if qualifying_boxes:
            self._hazard_streak += 1
        else:
            self._hazard_streak = 0

        if self._hazard_streak < self._confirmation_frames:
            cv2.putText(
                frame,
                "REAR PATH CLEAR",
                (20, 36),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 220, 0),
                2,
            )
            return frame, None

        largest_height = max(box[3] for box in qualifying_boxes)
        severity = "HIGH" if largest_height >= height * 0.28 else "WARNING"
        cv2.putText(
            frame,
            f"PEDESTRIAN IN REAR PATH - {severity}",
            (20, 36),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255),
            2,
        )
        return frame, {
            "hazard": "PEDESTRIAN_IN_REAR_PATH",
            "severity": severity,
            "zone": "REAR",
            "object_count": len(qualifying_boxes),
            "detection_source": "OPENCV_HOG",
        }


def run_rear_camera(
    camera_index: int = 0,
    v2x_service: V2XService | None = None,
    display: bool = True,
    stop_event: threading.Event | None = None,
    monitor_state: CameraMonitorState | None = None,
) -> None:
    """Read the camera, show detections, and rate-limit V2X hazard messages."""
    camera = cv2.VideoCapture(camera_index)
    if not camera.isOpened():
        message = f"Rear camera {camera_index} could not be opened"
        print(message)
        if monitor_state is not None:
            monitor_state.set_error(message)
        camera.release()
        return

    if monitor_state is not None:
        monitor_state.set_active()

    detector = RearCameraDetector()
    last_alert_at = 0.0
    alert_interval = 5.0
    try:
        while stop_event is None or not stop_event.is_set():
            success, frame = camera.read()
            if not success:
                message = "Rear camera frame could not be read"
                print(message)
                if monitor_state is not None:
                    monitor_state.set_error(message)
                break

            frame = cv2.flip(frame, 1)
            annotated, hazard = detector.process_frame(frame)
            if monitor_state is not None:
                monitor_state.record_frame(hazard)
            if hazard and time.monotonic() - last_alert_at >= alert_interval:
                print(f"[REAR CAMERA] {hazard['severity']}: pedestrian in rear path")
                if v2x_service is not None:
                    v2x_service.publish_safety_alert(hazard)
                last_alert_at = time.monotonic()

            if display:
                cv2.imshow("SVA Rear Camera", annotated)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    finally:
        camera.release()
        if monitor_state is not None:
            monitor_state.set_stopped()
        if display:
            cv2.destroyAllWindows()


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenCV rear-camera safety monitor")
    parser.add_argument("--camera-index", type=int, default=0)
    args = parser.parse_args()
    v2x_service = V2XService()
    if not v2x_service.enabled:
        print("V2X MQTT is not configured; local camera detection will still run")
    try:
        run_rear_camera(args.camera_index, v2x_service)
    except KeyboardInterrupt:
        pass
    finally:
        v2x_service.close()


if __name__ == "__main__":
    main()