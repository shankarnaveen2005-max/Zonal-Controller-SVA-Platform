from Laptop_cvc.digital_twin import DigitalTwin, _LandscapeCanvas
from Laptop_cvc.rear_camera import CameraMonitorState


class FakeCanvas:
    def create_rectangle(self, *coordinates, **_options):
        return coordinates

    def create_text(self, *coordinates, **_options):
        return coordinates


def test_desktop_vehicle_shapes_rotate_to_landscape() -> None:
    canvas = _LandscapeCanvas(FakeCanvas())

    rotated = canvas.create_rectangle(125, 30, 375, 325)

    assert rotated == (105, 50, 400, 300)


def test_desktop_text_coordinates_rotate_without_rotating_text() -> None:
    canvas = _LandscapeCanvas(FakeCanvas())

    rotated = canvas.create_text(250, 22, text="V2V LINK")

    assert rotated == (97, 175)


def test_desktop_camera_panel_shows_opencv_detection() -> None:
    class FakeLabel:
        def __init__(self):
            self.options = {}

        def config(self, **options):
            self.options = options

    twin = DigitalTwin.__new__(DigitalTwin)
    twin.camera_monitor_state = CameraMonitorState()
    twin.camera_monitor_state.set_active()
    twin.camera_monitor_state.record_frame({
        "hazard": "PEDESTRIAN_IN_REAR_PATH",
        "severity": "HIGH",
    })
    twin.camera_title = FakeLabel()
    twin.camera_message = FakeLabel()
    twin.camera_status_label = FakeLabel()

    twin._render_camera({})

    assert twin.camera_title.options["text"] == "PEDESTRIAN HIGH"
    assert twin.camera_message.options["text"] == "Detected in rear path"
    assert "ACTIVE" in twin.camera_status_label.options["text"]