import numpy as np

from Laptop_cvc.live_data import snapshot_from_cvc
from Laptop_cvc.rear_camera import CameraMonitorState, RearCameraDetector
from Laptop_cvc.v2x import V2XService


class FakeHogDetector:
    def detectMultiScale(self, _frame, **_kwargs):
        return [(100, 100, 100, 200)], []


def test_rear_path_pedestrian_requires_consecutive_frames() -> None:
    detector = RearCameraDetector(
        confirmation_frames=2,
        hog_detector=FakeHogDetector(),
    )
    frame = np.zeros((400, 400, 3), dtype=np.uint8)

    _, first_result = detector.process_frame(frame.copy())
    _, second_result = detector.process_frame(frame.copy())

    assert first_result is None
    assert second_result == {
        "hazard": "PEDESTRIAN_IN_REAR_PATH",
        "severity": "HIGH",
        "zone": "REAR",
        "object_count": 1,
        "detection_source": "OPENCV_HOG",
    }


def test_camera_monitor_state_reports_detection_and_camera_health() -> None:
    state = CameraMonitorState()
    state.set_active()
    state.record_frame({
        "hazard": "PEDESTRIAN_IN_REAR_PATH",
        "severity": "HIGH",
    })

    snapshot = state.snapshot()

    assert snapshot["available"] is True
    assert snapshot["status"] == "ACTIVE"
    assert snapshot["signal"] == "CONNECTED"
    assert snapshot["detection_status"] == "PEDESTRIAN IN REAR PATH"
    assert snapshot["hazard"]["severity"] == "HIGH"
    assert snapshot["last_frame_at"]

    state.set_error("Rear camera frame could not be read")
    failed_snapshot = state.snapshot()
    assert failed_snapshot["available"] is False
    assert failed_snapshot["status"] == "ERROR"
    assert failed_snapshot["error"] == "Rear camera frame could not be read"


def test_camera_monitor_state_is_included_in_vehicle_snapshot() -> None:
    from types import SimpleNamespace

    cvc = SimpleNamespace(
        zones={
            zone: SimpleNamespace(status="ONLINE", telemetry={})
            for zone in ("FRONT", "CABIN", "REAR")
        }
    )
    camera = CameraMonitorState()
    camera.set_active()
    camera.record_frame(None)

    snapshot = snapshot_from_cvc(cvc, camera_monitor_state=camera.snapshot())

    assert snapshot["camera"]["available"] is True
    assert snapshot["camera"]["detection_status"] == "CLEAR"
    assert snapshot["camera"]["last_frame_at"]


def test_v2x_publishes_camera_hazard_as_denm() -> None:
    class FakeMqttClient:
        published = None

        def publish(self, topic, message, qos):
            self.published = (topic, message, qos)

    service = V2XService.__new__(V2XService)
    service.vehicle_id = "test-vehicle"
    service.publish_topic = "test/v2x"
    service._client = FakeMqttClient()

    service.publish_safety_alert({"hazard": "PEDESTRIAN_IN_REAR_PATH"})

    topic, raw_message, qos = service._client.published
    from json import loads

    message = loads(raw_message)
    assert topic == "test/v2x"
    assert qos == 1
    assert message["message_type"] == "DENM"
    assert message["station_id"] == "test-vehicle"
    assert message["payload"]["hazard"] == "PEDESTRIAN_IN_REAR_PATH"