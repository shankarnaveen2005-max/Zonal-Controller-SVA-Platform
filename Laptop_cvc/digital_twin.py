"""Integrated SVA Digital Twin.

Features:
- Three STM32 Zonal ECU simulation
- ESP32 Gateway
- CAN communication
- Central Vehicle Computer
- Intelligent diagnostics / DTC
- Autonomous self-healing
- CSV data logging
- ML predictive maintenance
- Digital Twin visualization
- Scrollable CVC / ESP32 Gateway control panel
- OTA firmware update simulation
"""

import argparse
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk
from typing import Any

# Allow this file to import the dedicated Zonal_ECUs package when
# launched directly as: python Laptop_cvc/digital_twin.py
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from can_protocol import recovery_frame
from cvc_platform import CentralVehicleComputer, ZONES
from data_logging import DataLogger
from esp32_gateway import (
    ESP32Gateway,
    SerialGatewayTransport,
    SimulatedGatewayTransport,
)
from Zonal_ECUs.Front_ECU.front_ecu import FrontZonalECU
from Zonal_ECUs.Cabin_ECU.cabin_ecu import CabinZonalECU
from Zonal_ECUs.Rear_ECU.rear_ecu import RearZonalECU
from predictive_maintenance import (
    PredictiveMaintenance,
    ConditionData,
    apply_v2x_context,
)
from ota_manager import OTAManager
from live_data import MqttStatePublisher
from v2x import V2XService


# ============================================================
# GUI COLORS
# ============================================================

BG = "#101820"
PANEL = "#1b2935"
TEXT = "#e8f1f5"
GREEN = "#27c281"
RED = "#ef6262"
AMBER = "#f3b33d"
BLUE = "#6dd5fa"


class _LandscapeCanvas:
    """Rotate canvas drawing coordinates while preserving text orientation."""

    def __init__(self, canvas: tk.Canvas) -> None:
        self._canvas = canvas

    def __getattr__(self, name: str) -> Any:
        method = getattr(self._canvas, name)
        if name not in {"create_line", "create_oval", "create_polygon", "create_rectangle", "create_text"}:
            return method

        def create(*args: Any, **kwargs: Any) -> Any:
            coordinates = list(args)
            if name in {"create_oval", "create_rectangle"}:
                x1, y1, x2, y2 = coordinates[:4]
                points = (self._point(x1, y1), self._point(x2, y2))
                coordinates[:4] = (
                    min(points[0][0], points[1][0]),
                    min(points[0][1], points[1][1]),
                    max(points[0][0], points[1][0]),
                    max(points[0][1], points[1][1]),
                )
            elif name == "create_text":
                coordinates[0:2] = self._point(*coordinates[:2])
            else:
                coordinates = [
                    value
                    for point in zip(coordinates[::2], coordinates[1::2])
                    for value in self._point(*point)
                ]
            return method(*coordinates, **kwargs)

        return create

    @staticmethod
    def _point(x: float, y: float) -> tuple[float, float]:
        return y * 1.62 + 38, 425 - x


# ============================================================
# DIGITAL TWIN
# ============================================================

class DigitalTwin:

    def __init__(
        self,
        root: tk.Tk,
        port: str | None = None,
        baudrate: int = 115200,
        camera_index: int | None = None,
    ) -> None:

        self.root = root

        self.root.title(
            "SVA Digital Twin | Central Vehicle Computer"
        )

        self.root.geometry("1680x1050")
        self.root.minsize(1300, 800)
        self.root.configure(bg=BG)

        # ====================================================
        # ESP32 GATEWAY
        # ====================================================

        transport = (
            SerialGatewayTransport(port, baudrate)
            if port
            else SimulatedGatewayTransport()
        )

        self.gateway = ESP32Gateway(transport)

        # ====================================================
        # CENTRAL VEHICLE COMPUTER
        # ====================================================

        self.cvc = CentralVehicleComputer(
            self.gateway
        )

        # ====================================================
        # DATA LOGGER
        # ====================================================

        self.logger = DataLogger()

        # ====================================================
        # STM32 ZONAL ECU SIMULATION
        # ====================================================

        self.ecus = (
            {
                "FRONT": FrontZonalECU(),
                "CABIN": CabinZonalECU(),
                "REAR": RearZonalECU(),
            }
            if not port
            else {}
        )

        self.hardware_mode = port is not None
        self.elapsed = 0.0
        self.live_publisher = MqttStatePublisher()
        self.v2x = V2XService()
        self.v2x_alerts = []
        self.v2x_phase = 0
        self.camera_monitor_state = None
        self.camera_stop_event = None
        self.camera_thread = None

        if camera_index is not None:
            from rear_camera import CameraMonitorState, run_rear_camera

            self.camera_monitor_state = CameraMonitorState()
            self.camera_stop_event = threading.Event()
            self.camera_thread = threading.Thread(
                target=run_rear_camera,
                kwargs={
                    "camera_index": camera_index,
                    "v2x_service": self.v2x,
                    "display": False,
                    "stop_event": self.camera_stop_event,
                    "monitor_state": self.camera_monitor_state,
                },
                daemon=True,
            )
            self.camera_thread.start()

        # ====================================================
        # AUTONOMOUS RECOVERY
        # ====================================================

        self.recovery_requested = {
            zone: False
            for zone in ZONES
        }

        self.manual_faults: set[str] = set()

        self.ecu_controls: dict[
            str,
            tk.BooleanVar,
        ] = {}

        # ====================================================
        # ML PREDICTIVE MAINTENANCE
        # ====================================================

        self.predictive_system = (
            PredictiveMaintenance()
        )

        print(
            "\nTraining predictive maintenance model..."
        )

        accuracy = (
            self.predictive_system.train(
                samples_per_class=500
            )
        )

        print(
            f"Predictive maintenance model ready. "
            f"Test accuracy: {accuracy * 100:.2f}%\n"
        )

        self.condition_data = ConditionData(
            voltage=13.1,
            current=4.5,
            temperature=45.0,
            vibration=1.8,
            rpm=2200,
            communication_health=98.0,
        )

        self.ml_result = (
            self.predictive_system.predict(
                self.condition_data
            )
        )

        self.degradation_level = 0

        # ====================================================
        # OTA UPDATE SYSTEM
        # ====================================================

        self.ota_manager = OTAManager()

        self.ota_target = tk.StringVar(
            value="FRONT"
        )

        self.ota_new_version = tk.StringVar(
            value="v1.1.0"
        )

        self.ota_progress = tk.IntVar(
            value=0
        )

        self.ota_status = tk.StringVar(
            value="IDLE"
        )

        self.ota_updating = False

        # ====================================================
        # GUI STORAGE
        # ====================================================

        self.zone_items = {}
        self.door_items = {}
        self.belt_items = {}

        # ====================================================
        # BUILD GUI
        # ====================================================

        self._build_header()

        body = tk.Frame(
            self.root,
            bg=BG,
            height=460,
        )

        body.pack(
            fill="x",
            expand=False,
            padx=18,
            pady=(5, 5),
        )

        body.pack_propagate(False)

        self._build_vehicle_view(body)
        self._build_sidebar(body)
        self._build_bottom_panel()

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.tick()

    # ========================================================
    # HEADER
    # ========================================================

    def _build_header(self) -> None:

        header = tk.Frame(
            self.root,
            bg=BG,
        )

        header.pack(
            fill="x",
            padx=22,
            pady=(12, 4),
        )

        tk.Label(
            header,
            text="SOFTWARE VEHICLE ARCHITECTURE",
            fg=BLUE,
            bg=BG,
            font=("Arial", 25, "bold"),
        ).pack(anchor="w")

        tk.Label(
            header,
            text=(
                "ZONAL CONTROLLER-BASED ARCHITECTURE"
                "  •  DIGITAL TWIN"
                "  •  ML PREDICTIVE MAINTENANCE"
                "  •  OTA"
            ),
            fg=TEXT,
            bg=BG,
            font=("Arial", 11),
        ).pack(anchor="w")

    # ========================================================
    # VEHICLE VIEW
    # ========================================================

    def _build_vehicle_view(
        self,
        parent: tk.Frame,
    ) -> None:

        model_area = tk.Frame(parent, bg=BG)
        model_area.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(0, 10),
        )

        panel = tk.LabelFrame(
            model_area,
            text="LIVE VEHICLE MODEL",
            fg=TEXT,
            bg=PANEL,
            font=("Arial", 18, "bold"),
            padx=12,
            pady=8,
        )

        panel.pack(
            side="left",
            fill="both",
            expand=True,
        )

        self.canvas = tk.Canvas(
            panel,
            width=760,
            height=420,
            bg="#15232d",
            highlightthickness=0,
        )

        self.canvas.pack(
            fill="both",
            expand=True,
        )
        self._model_canvas = _LandscapeCanvas(self.canvas)

        self._model_canvas.create_rectangle(
            70,
            0,
            430,
            350,
            fill="#1d3039",
            outline="",
        )
        for x in (88, 412):
            for y in range(24, 340, 48):
                self._model_canvas.create_line(
                    x,
                    y,
                    x,
                    y + 24,
                    fill="#d6b86a",
                    width=2,
                )

        self.v2x_wave_items = [
            self._model_canvas.create_oval(
                82,
                18,
                418,
                332,
                outline="#4fd6e8",
                width=2,
                dash=(8, 12),
                tags=("v2x_wave",),
            ),
            self._model_canvas.create_oval(
                54,
                2,
                446,
                348,
                outline="#4fd6e8",
                width=2,
                dash=(8, 12),
                tags=("v2x_wave",),
            ),
            self._model_canvas.create_oval(
                24,
                -16,
                476,
                366,
                outline="#4fd6e8",
                width=2,
                dash=(8, 12),
                tags=("v2x_wave",),
            ),
        ]

        self.v2x_caption = self.canvas.create_text(
            325,
            22,
            text="V2V LINK · SIMULATION",
            fill="#7de8f5",
            font=("Arial", 13, "bold"),
        )

        self.canvas.create_text(
            48,
            175,
            text="◀ FRONT",
            fill="#d9e8ed",
            font=("Arial", 18, "bold"),
        )

        self.canvas.create_text(
            610,
            175,
            text="REAR ▶",
            fill="#d9e8ed",
            font=("Arial", 18, "bold"),
        )

        # Vehicle body - stylized top-view passenger car
        # The source coordinates are rotated and horizontally stretched by
        # _LandscapeCanvas so the vehicle fills the landscape panel and
        # keeps a recognizable long passenger-car proportion.
        self._model_canvas.create_polygon(
            # Distinct sedan silhouette: bumper -> hood -> cabin -> trunk.
            190, 22, 310, 22,          # front bumper
            338, 28, 354, 44,          # nose corners
            362, 72, 366, 105,         # front fenders
            354, 124,                   # A-pillar shoulder
            354, 238,                   # straight cabin side
            366, 252, 362, 286,         # rear fender
            348, 310, 320, 328,         # trunk shoulder
            180, 328, 152, 310,         # rear bumper/trunk
            138, 286, 134, 252,         # rear fender
            146, 238,                   # cabin side
            146, 124,                   # A-pillar shoulder
            134, 105, 138, 72,          # front fender
            146, 44, 162, 28,           # nose corners
            fill="#0b1116",
            outline="#d3e2e8",
            width=4,
        )

        # Bonnet / hood
        self._model_canvas.create_polygon(
            165, 36, 335, 36, 350, 54, 352, 100, 148, 100, 150, 54,
            fill="#172832", outline="#557581", width=2,
        )

        # Front windshield
        self._model_canvas.create_polygon(
            150, 108, 350, 108, 332, 138, 168, 138,
            fill="#294857", outline="#8fb8c7", width=2,
        )

        # Glass roof / cabin area
        self._model_canvas.create_polygon(
            168, 143, 332, 143, 342, 164, 342, 220, 332, 238,
            168, 238, 158, 220, 158, 164,
            fill="#182c37", outline="#557581", width=2,
        )

        # Rear windshield
        self._model_canvas.create_polygon(
            160, 244, 340, 244, 330, 270, 170, 270,
            fill="#294857", outline="#8fb8c7", width=2,
        )

        # Rear deck / trunk
        self._model_canvas.create_polygon(
            170, 276, 330, 276, 350, 308, 150, 308,
            fill="#172832", outline="#557581", width=2,
        )

        # Centre roof line
        self._model_canvas.create_line(
            250, 143, 250, 238, fill="#6f8994", width=1, dash=(5, 5)
        )

        # Side mirrors
        for x in (112, 374):
            self._model_canvas.create_oval(
                x, 112, x + 14, 132, fill="#111b21", outline="#91aab5", width=2
            )

        # Wheels with inner rims
        for x in (105, 375):
            for y in (72, 238):
                self._model_canvas.create_oval(
                    x, y, x + 24, y + 52,
                    fill="#030608", outline="#738b95", width=2,
                )
                self._model_canvas.create_oval(
                    x + 5, y + 10, x + 19, y + 42,
                    fill="#26343b", outline="#8fa3ab", width=1,
                )

        # Headlights
        for x in (166, 314):
            self._model_canvas.create_oval(
                x, 29, x + 22, 42, fill="#f6d36b", outline="#fff0a8", width=2
            )

        # Tail lights
        for x in (166, 314):
            self._model_canvas.create_oval(
                x, 312, x + 22, 325, fill="#e85a5a", outline="#ff9b9b", width=2
            )

        # Front and rear bumpers
        self._model_canvas.create_line(
            185, 25, 315, 25, fill="#d8e7ec", width=4
        )
        self._model_canvas.create_line(
            185, 329, 315, 329, fill="#657f8a", width=4
        )

        # Zonal ECU overlays.  Each region is given enough longitudinal
        # space for its ECU name and CAN IDs to remain inside the car.
        self._zone(
            "FRONT", 175, 45, 325, 118, "0x101 / 0x102"
        )

        self._zone(
            "CABIN", 165, 126, 335, 244, "0x201 / 0x202"
        )

        self._zone(
            "REAR", 175, 252, 325, 320, "0x301 / 0x302"
        )

        self._draw_car_details()
        self._build_camera_panel(model_area)

    def _build_camera_panel(self, parent: tk.Frame) -> None:
        """Reserve a rear-camera area for future hardware input."""
        panel = tk.LabelFrame(
            parent,
            text="REAR CAMERA",
            fg=TEXT,
            bg=PANEL,
            font=("Arial", 14, "bold"),
            padx=10,
            pady=10,
            width=330,
        )
        panel.pack(side="right", fill="y", padx=(12, 0))
        panel.pack_propagate(False)

        self.camera_screen = tk.Frame(panel, bg="#030609", height=210)
        self.camera_screen.pack(fill="x", pady=(4, 10))
        self.camera_screen.pack_propagate(False)

        self.camera_title = tk.Label(
            self.camera_screen,
            text="NO SIGNAL",
            fg=RED,
            bg="#030609",
            font=("Arial", 20, "bold"),
        )
        self.camera_title.pack(expand=True)

        self.camera_message = tk.Label(
            self.camera_screen,
            text="Camera Not Connected",
            fg="#9bb0b8",
            bg="#030609",
            font=("Arial", 12),
        )
        self.camera_message.pack(pady=(0, 25))

        self.camera_status_label = tk.Label(
            panel,
            text="Status : OFFLINE\nSignal : NO SIGNAL\nLocation: REAR",
            fg=RED,
            bg=PANEL,
            justify="left",
            anchor="w",
            font=("Courier", 11, "bold"),
        )
        self.camera_status_label.pack(fill="x", pady=4)

        tk.Label(
            panel,
            text=(
                "OpenCV rear-path monitor enabled with --rear-camera"
                if self.camera_monitor_state is not None
                else "Connect rear camera with --rear-camera"
            ),
            fg="#9bb0b8",
            bg=PANEL,
            justify="left",
            wraplength=290,
            font=("Arial", 11),
        ).pack(fill="x", pady=(10, 0))

    def close(self) -> None:
        """Close network resources and the desktop twin."""
        if self.camera_stop_event is not None:
            self.camera_stop_event.set()
            if self.camera_thread is not None:
                self.camera_thread.join(timeout=2)
        for service in (self.live_publisher, self.v2x):
            close = getattr(service, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass
        self.root.destroy()

    # ========================================================
    # VEHICLE DETAILS
    # ========================================================

    def _draw_car_details(self) -> None:
        """Draw doors, seats and cabin details inside the car silhouette."""

        # Four doors follow the side profile of the passenger compartment.
        for side, x in (("left", 150), ("right", 350)):
            for position, y in (("front", 145), ("rear", 194)):
                key = f"{position}_{side}"
                x2 = x + 9 if side == "left" else x - 9
                self.door_items[key] = self._model_canvas.create_rectangle(
                    x, y, x2, y + 40,
                    fill="#28563f", outline=GREEN, width=2,
                )
                self._model_canvas.create_line(
                    x2, y + 20,
                    x2 + (7 if side == "left" else -7), y + 20,
                    fill="#b3c5cc", width=2,
                )

        # Four seats.  Smaller seat shapes keep the CABIN ECU label readable.
        seats = {
            "driver": (180, 155),
            "front_passenger": (270, 155),
            "rear_left": (180, 202),
            "rear_right": (270, 202),
        }

        for key, (x, y) in seats.items():
            self._model_canvas.create_rectangle(
                x, y, x + 48, y + 34,
                fill="#344b59", outline="#b3c5cc", width=2,
            )
            # Headrest
            self._model_canvas.create_rectangle(
                x + 12, y + 3, x + 36, y + 9,
                fill="#405c6a", outline="#78909a", width=1,
            )
            self.belt_items[key] = self._model_canvas.create_line(
                x + 8, y + 9, x + 40, y + 29,
                fill=GREEN, width=3,
            )

        # Steering wheel on the driver side.
        self._model_canvas.create_oval(
            185, 143, 215, 166, outline="#d2e0e5", width=2
        )


    # ========================================================
    # ZONAL ECU GRAPHICS
    # ========================================================

    def _zone(
        self,
        zone: str,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        can_ids: str,
    ) -> None:

        item = self._model_canvas.create_rectangle(
            x1,
            y1,
            x2,
            y2,
            fill="#244936",
            outline=GREEN,
            width=2,
        )

        self.zone_items[zone] = item

        # Keep the complete description inside its own zone.  The landscape
        # coordinate transform makes the longitudinal zone dimension the
        # available text width, so compact multi-line labels avoid overlap.
        if zone == "CABIN":
            label = f"CABIN ZONAL ECU\nCAN ID: {can_ids}"
            label_font = ("Arial", 11, "bold")
            text_width = 108
        else:
            label = f"{zone} ZONAL ECU\nCAN ID\n{can_ids}"
            label_font = ("Arial", 10, "bold")
            text_width = 64

        self._model_canvas.create_text(
            (x1 + x2) / 2,
            (y1 + y2) / 2,
            text=label,
            fill=TEXT,
            font=label_font,
            width=text_width,
            justify="center",
        )

    # ========================================================
    # SCROLLABLE CVC / ESP32 SIDEBAR
    # ========================================================

    def _build_sidebar(
        self,
        parent: tk.Frame,
    ) -> None:

        outer_panel = tk.LabelFrame(
            parent,
            text="CVC / ESP32 GATEWAY",
            fg=TEXT,
            bg=PANEL,
            font=("Arial", 12, "bold"),
            padx=4,
            pady=4,
            width=350,
        )

        outer_panel.pack(
            side="right",
            fill="y",
        )

        outer_panel.pack_propagate(False)

        sidebar_canvas = tk.Canvas(
            outer_panel,
            bg=PANEL,
            highlightthickness=0,
            borderwidth=0,
        )

        sidebar_scrollbar = ttk.Scrollbar(
            outer_panel,
            orient="vertical",
            command=sidebar_canvas.yview,
        )

        sidebar_canvas.configure(
            yscrollcommand=sidebar_scrollbar.set
        )

        sidebar_scrollbar.pack(
            side="right",
            fill="y",
        )

        sidebar_canvas.pack(
            side="left",
            fill="both",
            expand=True,
        )

        panel = tk.Frame(
            sidebar_canvas,
            bg=PANEL,
        )

        sidebar_window = (
            sidebar_canvas.create_window(
                (0, 0),
                window=panel,
                anchor="nw",
            )
        )

        def update_scroll_region(
            event=None,
        ):

            sidebar_canvas.configure(
                scrollregion=(
                    sidebar_canvas.bbox("all")
                )
            )

        panel.bind(
            "<Configure>",
            update_scroll_region,
        )

        def update_content_width(event):

            sidebar_canvas.itemconfigure(
                sidebar_window,
                width=event.width,
            )

        sidebar_canvas.bind(
            "<Configure>",
            update_content_width,
        )

        # ====================================================
        # MOUSE / TRACKPAD SCROLL
        # ====================================================

        def mouse_scroll(event):

            if event.delta == 0:
                return

            direction = (
                -1
                if event.delta > 0
                else 1
            )

            sidebar_canvas.yview_scroll(
                direction,
                "units",
            )

        def linux_scroll_up(event):

            sidebar_canvas.yview_scroll(
                -1,
                "units",
            )

        def linux_scroll_down(event):

            sidebar_canvas.yview_scroll(
                1,
                "units",
            )

        def enable_scrolling(event=None):

            sidebar_canvas.bind_all(
                "<MouseWheel>",
                mouse_scroll,
            )

            sidebar_canvas.bind_all(
                "<Button-4>",
                linux_scroll_up,
            )

            sidebar_canvas.bind_all(
                "<Button-5>",
                linux_scroll_down,
            )

        def disable_scrolling(event=None):

            sidebar_canvas.unbind_all(
                "<MouseWheel>"
            )

            sidebar_canvas.unbind_all(
                "<Button-4>"
            )

            sidebar_canvas.unbind_all(
                "<Button-5>"
            )

        outer_panel.bind(
            "<Enter>",
            enable_scrolling,
        )

        outer_panel.bind(
            "<Leave>",
            disable_scrolling,
        )

        sidebar_canvas.bind(
            "<Enter>",
            enable_scrolling,
        )

        panel.bind(
            "<Enter>",
            enable_scrolling,
        )

        # ====================================================
        # NETWORK HEALTH
        # ====================================================

        self.health_label = tk.Label(
            panel,
            text="● STARTING",
            fg=AMBER,
            bg=PANEL,
            font=("Arial", 16, "bold"),
        )

        self.health_label.pack(
            pady=(10, 7),
        )

        # ====================================================
        # GATEWAY STATUS
        # ====================================================

        self.gateway_label = tk.Label(
            panel,
            text=(
                "ESP32 Gateway  STARTING\n\n"
                "FRONT   STARTING\n"
                "CABIN   STARTING\n"
                "REAR    STARTING"
            ),
            fg=TEXT,
            bg=PANEL,
            justify="left",
            anchor="w",
            font=("Courier", 10),
        )

        self.gateway_label.pack(
            fill="x",
            padx=15,
            pady=4,
        )

        # ====================================================
        # SELF HEALING
        # ====================================================

        ttk.Separator(
            panel
        ).pack(
            fill="x",
            padx=12,
            pady=8,
        )

        tk.Label(
            panel,
            text="SELF-HEALING / RECOVERY",
            fg=BLUE,
            bg=PANEL,
            font=("Arial", 10, "bold"),
        ).pack(
            anchor="w",
            padx=15,
        )

        self.recovery_label = tk.Label(
            panel,
            text=(
                "FRONT  IDLE       Attempts: 0\n"
                "CABIN  IDLE       Attempts: 0\n"
                "REAR   IDLE       Attempts: 0"
            ),
            fg=TEXT,
            bg=PANEL,
            justify="left",
            anchor="w",
            font=("Courier", 9),
        )

        self.recovery_label.pack(
            fill="x",
            padx=15,
            pady=(5, 8),
        )

        # ====================================================
        # FAULT INJECTION
        # ====================================================

        ttk.Separator(
            panel
        ).pack(
            fill="x",
            padx=12,
            pady=8,
        )

        tk.Label(
            panel,
            text="FAULT INJECTION",
            fg=AMBER,
            bg=PANEL,
            font=("Arial", 10, "bold"),
        ).pack(
            anchor="w",
            padx=15,
            pady=(0, 5),
        )

        for zone in ZONES:

            control = tk.BooleanVar(
                value=True
            )

            self.ecu_controls[
                zone
            ] = control

            ttk.Checkbutton(
                panel,
                text=(
                    f"{zone.title()} ECU online"
                ),
                variable=control,
                command=(
                    lambda selected=zone:
                    self.toggle_ecu(selected)
                ),
            ).pack(
                fill="x",
                padx=15,
                pady=2,
            )

        ttk.Button(
            panel,
            text="Toggle ESP32 Gateway",
            command=self.toggle_gateway,
        ).pack(
            fill="x",
            padx=15,
            pady=3,
        )

        ttk.Button(
            panel,
            text="Clear faults / restore network",
            command=self.restore_network,
        ).pack(
            fill="x",
            padx=15,
            pady=3,
        )

        # ====================================================
        # ML CONDITION SIMULATION
        # ====================================================

        ttk.Separator(
            panel
        ).pack(
            fill="x",
            padx=12,
            pady=8,
        )

        tk.Label(
            panel,
            text="ML CONDITION SIMULATION",
            fg=BLUE,
            bg=PANEL,
            font=("Arial", 10, "bold"),
        ).pack(
            anchor="w",
            padx=15,
            pady=(0, 5),
        )

        ttk.Button(
            panel,
            text="Simulate Degradation",
            command=self.simulate_degradation,
        ).pack(
            fill="x",
            padx=15,
            pady=3,
        )

        ttk.Button(
            panel,
            text="Reset Vehicle Condition",
            command=self.reset_condition,
        ).pack(
            fill="x",
            padx=15,
            pady=3,
        )

        ttk.Button(
            panel,
            text="Run ML Prediction",
            command=self.run_ml_prediction,
        ).pack(
            fill="x",
            padx=15,
            pady=3,
        )

        # ====================================================
        # OTA FIRMWARE UPDATE
        # ====================================================

        ttk.Separator(
            panel
        ).pack(
            fill="x",
            padx=12,
            pady=10,
        )

        tk.Label(
            panel,
            text="OTA FIRMWARE UPDATE",
            fg=BLUE,
            bg=PANEL,
            font=("Arial", 10, "bold"),
        ).pack(
            anchor="w",
            padx=15,
            pady=(0, 7),
        )

        tk.Label(
            panel,
            text="Target Zonal ECU",
            fg=TEXT,
            bg=PANEL,
            font=("Arial", 10),
        ).pack(
            anchor="w",
            padx=15,
        )

        self.ota_zone_box = ttk.Combobox(
            panel,
            textvariable=self.ota_target,
            values=ZONES,
            state="readonly",
        )

        self.ota_zone_box.pack(
            fill="x",
            padx=15,
            pady=(2, 7),
        )

        self.ota_zone_box.bind(
            "<<ComboboxSelected>>",
            self._ota_target_changed,
        )

        self.ota_current_version_label = (
            tk.Label(
                panel,
                text=(
                    "Current Firmware: "
                    "v1.0.0"
                ),
                fg=TEXT,
                bg=PANEL,
                font=(
                    "Courier",
                    9,
                    "bold",
                ),
            )
        )

        self.ota_current_version_label.pack(
            anchor="w",
            padx=15,
            pady=3,
        )

        tk.Label(
            panel,
            text="New Firmware Version",
            fg=TEXT,
            bg=PANEL,
            font=("Arial", 10),
        ).pack(
            anchor="w",
            padx=15,
            pady=(6, 0),
        )

        self.ota_version_entry = (
            ttk.Entry(
                panel,
                textvariable=(
                    self.ota_new_version
                ),
            )
        )

        self.ota_version_entry.pack(
            fill="x",
            padx=15,
            pady=(2, 7),
        )

        self.ota_update_button = (
            ttk.Button(
                panel,
                text="Start OTA Update",
                command=(
                    self.start_ota_update
                ),
            )
        )

        self.ota_update_button.pack(
            fill="x",
            padx=15,
            pady=5,
        )

        self.ota_progress_bar = (
            ttk.Progressbar(
                panel,
                variable=self.ota_progress,
                maximum=100,
                mode="determinate",
            )
        )

        self.ota_progress_bar.pack(
            fill="x",
            padx=15,
            pady=(8, 3),
        )

        self.ota_progress_label = (
            tk.Label(
                panel,
                text="Progress: 0%",
                fg=TEXT,
                bg=PANEL,
                font=("Courier", 10),
            )
        )

        self.ota_progress_label.pack(
            anchor="w",
            padx=15,
        )

        self.ota_status_label = (
            tk.Label(
                panel,
                text="Status: IDLE",
                fg=TEXT,
                bg=PANEL,
                justify="left",
                anchor="w",
                font=(
                    "Courier",
                    9,
                    "bold",
                ),
            )
        )

        self.ota_status_label.pack(
            fill="x",
            padx=15,
            pady=(4, 15),
        )

        # Extra bottom spacing
        tk.Frame(
            panel,
            bg=PANEL,
            height=25,
        ).pack()

    # ========================================================
    # BOTTOM PANELS
    # ========================================================

    def _build_bottom_panel(self) -> None:

        panel = tk.Frame(
            self.root,
            bg=BG,
            height=440,
        )

        panel.pack(
            fill="x",
            expand=False,
            padx=18,
            pady=(5, 15),
        )

        panel.pack_propagate(False)

        # ====================================================
        # TELEMETRY
        # ====================================================

        telemetry_panel = tk.LabelFrame(
            panel,
            text="VEHICLE TELEMETRY",
            fg=TEXT,
            bg=PANEL,
            font=("Arial", 15, "bold"),
            padx=12,
            pady=10,
        )

        telemetry_panel.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(0, 5),
        )

        self.telemetry_label = tk.Label(
            telemetry_panel,
            text=(
                "Waiting for vehicle telemetry..."
            ),
            fg=TEXT,
            bg=PANEL,
            justify="left",
            anchor="nw",
            font=("Courier", 12, "bold"),
        )

        self.telemetry_label.pack(
            fill="both",
            expand=True,
        )

        # ====================================================
        # DIAGNOSTICS
        # ====================================================

        diagnostic_panel = tk.LabelFrame(
            panel,
            text="INTELLIGENT DIAGNOSTICS",
            fg=TEXT,
            bg=PANEL,
            font=("Arial", 15, "bold"),
            padx=12,
            pady=10,
        )

        diagnostic_panel.pack(
            side="left",
            fill="both",
            expand=True,
            padx=5,
        )

        self.diagnostic_label = tk.Label(
            diagnostic_panel,
            text=(
                "Starting diagnostic system..."
            ),
            fg=GREEN,
            bg=PANEL,
            justify="left",
            anchor="nw",
            font=("Courier", 12, "bold"),
            wraplength=430,
        )

        self.diagnostic_label.pack(
            fill="both",
            expand=True,
        )

        # ====================================================
        # ML
        # ====================================================

        ml_panel = tk.LabelFrame(
            panel,
            text="ML PREDICTIVE MAINTENANCE",
            fg=TEXT,
            bg=PANEL,
            font=("Arial", 15, "bold"),
            padx=12,
            pady=10,
        )

        ml_panel.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(5, 0),
        )

        self.ml_label = tk.Label(
            ml_panel,
            text=(
                "Initializing ML predictive "
                "maintenance..."
            ),
            fg=GREEN,
            bg=PANEL,
            justify="left",
            anchor="nw",
            font=("Courier", 12, "bold"),
            wraplength=430,
        )

        self.ml_label.pack(
            fill="both",
            expand=True,
        )

    # ========================================================
    # ECU FAULT
    # ========================================================

    def toggle_ecu(
        self,
        zone: str,
    ) -> None:

        if self.hardware_mode:

            self.ecu_controls[
                zone
            ].set(True)

            return

        ecu = self.ecus[zone]

        requested_online = (
            self.ecu_controls[
                zone
            ].get()
        )

        ecu.online = requested_online

        if requested_online:

            self.manual_faults.discard(
                zone
            )

            self.recovery_requested[
                zone
            ] = False

            state = self.cvc.zones[
                zone
            ]

            state.recovery_status = "IDLE"

        else:

            self.manual_faults.add(
                zone
            )

            state = self.cvc.zones[
                zone
            ]

            state.status = "OFFLINE"
            state.last_heartbeat = None

            state.recovery_status = (
                "MANUAL OFFLINE"
            )

            self.recovery_requested[
                zone
            ] = False

    # ========================================================
    # GATEWAY FAULT
    # ========================================================

    def toggle_gateway(self) -> None:

        if isinstance(
            self.gateway.transport,
            SimulatedGatewayTransport,
        ):

            self.gateway.transport.connected = (
                not
                self.gateway.transport.connected
            )

    # ========================================================
    # RESTORE NETWORK
    # ========================================================

    def restore_network(self) -> None:

        if self.hardware_mode:
            return

        if isinstance(
            self.gateway.transport,
            SimulatedGatewayTransport,
        ):

            self.gateway.transport.connected = True

        for zone, ecu in self.ecus.items():

            ecu.online = True

            self.manual_faults.discard(
                zone
            )

            self.ecu_controls[
                zone
            ].set(True)

            self.recovery_requested[
                zone
            ] = False

            state = self.cvc.zones[
                zone
            ]

            state.recovery_status = "IDLE"
            state.recovery_attempts = 0

    # ========================================================
    # DOORS
    # ========================================================

    def toggle_doors(self) -> None:

        if self.hardware_mode:
            return

        cabin = self.ecus[
            "CABIN"
        ].telemetry()

        if cabin is None:
            return

        doors = cabin.payload[
            "doors"
        ]

        new_state = (
            "OPEN"
            if all(
                state == "CLOSED"
                for state
                in doors.values()
            )
            else "CLOSED"
        )

        self.ecus[
            "CABIN"
        ].door_state = new_state

    # ========================================================
    # SEAT BELTS
    # ========================================================

    def toggle_seatbelts(self) -> None:

        if self.hardware_mode:
            return

        cabin = self.ecus[
            "CABIN"
        ].telemetry()

        if cabin is None:
            return

        belts = cabin.payload[
            "seatbelts"
        ]

        new_state = (
            "WORN"
            if all(
                state == "NOT WORN"
                for state
                in belts.values()
            )
            else "NOT WORN"
        )

        self.ecus[
            "CABIN"
        ].belt_state = new_state

    # ========================================================
    # ML DEGRADATION
    # ========================================================

    def simulate_degradation(self) -> None:

        if self.hardware_mode:
            return

        self.degradation_level += 1

        if self.degradation_level == 1:

            self.condition_data = ConditionData(
                voltage=12.0,
                current=8.0,
                temperature=66.0,
                vibration=3.7,
                rpm=3600,
                communication_health=88.0,
            )

        elif self.degradation_level == 2:

            self.condition_data = ConditionData(
                voltage=11.7,
                current=9.2,
                temperature=75.0,
                vibration=4.6,
                rpm=4200,
                communication_health=78.0,
            )

        else:

            self.degradation_level = 3

            self.condition_data = ConditionData(
                voltage=10.4,
                current=14.0,
                temperature=98.0,
                vibration=8.2,
                rpm=5900,
                communication_health=40.0,
            )

        self.run_ml_prediction()

    # ========================================================
    # RESET CONDITION
    # ========================================================

    def reset_condition(self) -> None:

        self.degradation_level = 0

        self.condition_data = ConditionData(
            voltage=13.1,
            current=4.5,
            temperature=45.0,
            vibration=1.8,
            rpm=2200,
            communication_health=98.0,
        )

        self.run_ml_prediction()

    # ========================================================
    # ML PREDICTION
    # ========================================================

    def run_ml_prediction(self) -> None:

        self.ml_result = (
            self.predictive_system.predict(
                self.condition_data
            )
        )

        self._render_ml()

    def _render_camera(self, rear: dict) -> None:
        """Render OpenCV status when enabled, otherwise use ECU camera telemetry."""
        if self.camera_monitor_state is not None:
            camera = self.camera_monitor_state.snapshot()
            status = str(camera["status"]).upper()
            signal = str(camera["signal"]).upper()
            location = str(camera["location"]).upper()
            available = camera["available"]
            hazard = camera["hazard"]
            if available and hazard:
                title = f"PEDESTRIAN {hazard.get('severity', 'WARNING')}"
                message = "Detected in rear path"
                color = RED
            elif available:
                title = "CAMERA ACTIVE"
                message = "Rear path clear"
                color = GREEN
            elif camera["error"]:
                title = "CAMERA ERROR"
                message = str(camera["error"])
                color = RED
            else:
                title = "CAMERA STARTING"
                message = "Waiting for camera frames"
                color = AMBER
        else:
            status = str(rear.get("camera_status", "OFFLINE")).upper()
            signal = str(rear.get("camera_signal", "NO SIGNAL")).upper()
            location = str(rear.get("camera_location", "REAR")).upper()
            available = rear.get("camera_available", False)
            ready = status == "ONLINE" and signal not in {"NO SIGNAL", "OFFLINE"}

            if ready or available:
                title = "CAMERA READY"
                message = "Waiting for video stream"
                color = GREEN
            else:
                title = "NO SIGNAL"
                message = "Camera Not Connected"
                color = RED

        self.camera_title.config(text=title, fg=color)
        self.camera_message.config(text=message)
        self.camera_status_label.config(
            text=f"Status : {status}\nSignal : {signal}\nLocation: {location}",
            fg=color,
        )

    # ========================================================
    # OTA TARGET CHANGE
    # ========================================================

    def _ota_target_changed(
        self,
        event=None,
    ) -> None:

        zone = self.ota_target.get()

        version = (
            self.ota_manager.get_version(
                zone
            )
        )

        self.ota_current_version_label.config(
            text=(
                f"Current Firmware: "
                f"{version}"
            )
        )

        self.ota_progress.set(0)

        self.ota_progress_label.config(
            text="Progress: 0%"
        )

        self.ota_status_label.config(
            text="Status: IDLE",
            fg=TEXT,
        )

    # ========================================================
    # START OTA
    # ========================================================

    def start_ota_update(self) -> None:

        if self.ota_updating:
            return

        zone = self.ota_target.get()

        new_version = (
            self.ota_new_version.get().strip()
        )

        if not new_version:

            self.ota_status_label.config(
                text=(
                    "Status: INVALID VERSION"
                ),
                fg=RED,
            )

            return

        if (
            self.cvc.zones[
                zone
            ].status != "ONLINE"
        ):

            self.ota_status_label.config(
                text=(
                    "Status: TARGET ECU OFFLINE"
                ),
                fg=RED,
            )

            return

        if not self.gateway.connected:

            self.ota_status_label.config(
                text=(
                    "Status: GATEWAY DISCONNECTED"
                ),
                fg=RED,
            )

            return

        current_version = (
            self.ota_manager.get_version(
                zone
            )
        )

        if current_version == new_version:

            self.ota_progress.set(100)

            self.ota_progress_label.config(
                text="Progress: 100%"
            )

            self.ota_status_label.config(
                text="Status: UP TO DATE",
                fg=GREEN,
            )

            return

        self.ota_updating = True

        self.ota_update_button.config(
            state="disabled"
        )

        self.ota_zone_box.config(
            state="disabled"
        )

        self.ota_version_entry.config(
            state="disabled"
        )

        self.ota_progress.set(0)

        self.ota_progress_label.config(
            text="Progress: 0%"
        )

        self.ota_status_label.config(
            text="Status: PREPARING UPDATE",
            fg=AMBER,
        )

        self.root.after(
            400,
            lambda: self._ota_download(
                zone,
                new_version,
                0,
            ),
        )

    # ========================================================
    # OTA DOWNLOAD
    # ========================================================

    def _ota_download(
        self,
        zone: str,
        new_version: str,
        progress: int,
    ) -> None:

        if not self.gateway.connected:

            self._ota_failed(
                "GATEWAY CONNECTION LOST"
            )

            return

        if (
            self.cvc.zones[
                zone
            ].status != "ONLINE"
        ):

            self._ota_failed(
                f"{zone} ECU OFFLINE"
            )

            return

        self.ota_status_label.config(
            text=(
                f"Status: DOWNLOADING TO "
                f"{zone}"
            ),
            fg=AMBER,
        )

        self.ota_progress.set(
            progress
        )

        self.ota_progress_label.config(
            text=(
                f"Progress: {progress}%"
            )
        )

        if progress < 60:

            self.root.after(
                250,
                lambda: self._ota_download(
                    zone,
                    new_version,
                    progress + 10,
                ),
            )

        else:

            self.root.after(
                400,
                lambda: self._ota_verify(
                    zone,
                    new_version,
                ),
            )

    # ========================================================
    # OTA VERIFY
    # ========================================================

    def _ota_verify(
        self,
        zone: str,
        new_version: str,
    ) -> None:

        if not self.gateway.connected:

            self._ota_failed(
                "GATEWAY CONNECTION LOST"
            )

            return

        self.ota_status_label.config(
            text="Status: VERIFYING FIRMWARE",
            fg=AMBER,
        )

        self.ota_progress.set(70)

        self.ota_progress_label.config(
            text="Progress: 70%"
        )

        self.root.after(
            600,
            lambda: self._ota_install(
                zone,
                new_version,
            ),
        )

    # ========================================================
    # OTA INSTALL
    # ========================================================

    def _ota_install(
        self,
        zone: str,
        new_version: str,
    ) -> None:

        if not self.gateway.connected:

            self._ota_failed(
                "GATEWAY CONNECTION LOST"
            )

            return

        self.ota_status_label.config(
            text="Status: INSTALLING FIRMWARE",
            fg=AMBER,
        )

        self.ota_progress.set(85)

        self.ota_progress_label.config(
            text="Progress: 85%"
        )

        self.root.after(
            600,
            lambda: self._ota_restart(
                zone,
                new_version,
            ),
        )

    # ========================================================
    # OTA RESTART
    # ========================================================

    def _ota_restart(
        self,
        zone: str,
        new_version: str,
    ) -> None:

        self.ota_status_label.config(
            text=(
                f"Status: RESTARTING "
                f"{zone} ECU"
            ),
            fg=AMBER,
        )

        self.ota_progress.set(95)

        self.ota_progress_label.config(
            text="Progress: 95%"
        )

        # Simulated restart only.
        if not self.hardware_mode:

            self.ecus[
                zone
            ].online = False

        self.root.after(
            700,
            lambda: self._ota_complete(
                zone,
                new_version,
            ),
        )

    # ========================================================
    # OTA COMPLETE
    # ========================================================

    def _ota_complete(
        self,
        zone: str,
        new_version: str,
    ) -> None:

        if not self.gateway.connected:

            self._ota_failed(
                "GATEWAY CONNECTION LOST"
            )

            return

        if not self.hardware_mode:

            self.ecus[
                zone
            ].online = True

        self.ota_manager.firmware_versions[
            zone
        ] = new_version

        self.ota_manager.update_status[
            zone
        ] = "COMPLETED"

        self.ota_manager.progress[
            zone
        ] = 100

        self.ota_progress.set(100)

        self.ota_progress_label.config(
            text="Progress: 100%"
        )

        self.ota_current_version_label.config(
            text=(
                f"Current Firmware: "
                f"{new_version}"
            )
        )

        self.ota_status_label.config(
            text=(
                "Status: COMPLETED\n"
                f"{zone} ECU → {new_version}"
            ),
            fg=GREEN,
        )

        self.ota_updating = False

        self.ota_update_button.config(
            state="normal"
        )

        self.ota_zone_box.config(
            state="readonly"
        )

        self.ota_version_entry.config(
            state="normal"
        )

    # ========================================================
    # OTA FAILED
    # ========================================================

    def _ota_failed(
        self,
        reason: str,
    ) -> None:

        self.ota_updating = False

        self.ota_status_label.config(
            text=(
                "Status: FAILED\n"
                f"{reason}"
            ),
            fg=RED,
        )

        self.ota_update_button.config(
            state="normal"
        )

        self.ota_zone_box.config(
            state="readonly"
        )

        self.ota_version_entry.config(
            state="normal"
        )

    # ========================================================
    # AUTOMATIC SELF HEALING
    # ========================================================

    def _automatic_recovery(self) -> None:

        if self.hardware_mode:
            return

        if not self.gateway.connected:
            return

        for zone in ZONES:

            if zone in self.manual_faults:
                continue

            state = self.cvc.zones[
                zone
            ]

            if (
                state.status == "OFFLINE"
                and not
                self.recovery_requested[
                    zone
                ]
            ):

                self.cvc.request_recovery(
                    zone
                )

                command = recovery_frame(
                    zone
                )

                self.ecus[
                    zone
                ].process_command(
                    command
                )

                self.recovery_requested[
                    zone
                ] = True

            if (
                self.recovery_requested[
                    zone
                ]
                and
                state.recovery_status
                == "RECOVERED"
            ):

                self.recovery_requested[
                    zone
                ] = False

    # ========================================================
    # MAIN LOOP
    # ========================================================

    def tick(self) -> None:

        try:

            if not self.hardware_mode:

                for ecu in self.ecus.values():

                    if not ecu.online:
                        continue

                    # Dedicated zonal ECU simulation:
                    # refresh local sensor values before transmission.
                    ecu.update_sensors()

                    heartbeat = ecu.heartbeat()
                    telemetry = ecu.telemetry()

                    for frame in (
                        heartbeat,
                        telemetry,
                    ):

                        if (
                            frame
                            and
                            self.gateway.connected
                        ):

                            self.gateway.send(
                                frame
                            )

                self.cvc.poll(
                    self.elapsed
                )

                self._automatic_recovery()

            else:

                self.cvc.poll()

            # =================================================
            # NETWORK HEALTH
            # =================================================

            online_count = sum(
                self.cvc.zones[
                    zone
                ].status == "ONLINE"
                for zone in ZONES
            )

            network_health = (
                online_count
                / len(ZONES)
            ) * 100.0

            if not self.gateway.connected:

                network_health = 0.0

            communication_health = network_health

            self.condition_data = (
                ConditionData(
                    voltage=(
                        self.condition_data.voltage
                    ),
                    current=(
                        self.condition_data.current
                    ),
                    temperature=(
                        self.condition_data.temperature
                    ),
                    vibration=(
                        self.condition_data.vibration
                    ),
                    rpm=(
                        self.condition_data.rpm
                    ),
                    communication_health=(
                        communication_health
                    ),
                )
            )

            self.ml_result = (
                self.predictive_system.predict(
                    self.condition_data
                )
            )

            self.v2x_alerts.extend(self.v2x.receive_alerts())
            self.v2x_alerts = self.v2x_alerts[-20:]
            self.ml_result = apply_v2x_context(
                self.ml_result,
                self.v2x_alerts,
            )

            self._animate_v2x()

            # =================================================
            # DATA LOGGING
            # =================================================

            self.logger.log(
                self.cvc
            )

            snapshot = self.cvc.vehicle_snapshot()
            if self.camera_monitor_state is not None:
                snapshot["camera"] = self.camera_monitor_state.snapshot()
            snapshot["v2x"] = {
                "status": "ALERT" if self.v2x_alerts else "CLEAR",
                "alerts": [
                    {
                        "message_type": alert.message_type,
                        "station_id": alert.station_id,
                        "timestamp": alert.timestamp,
                        "payload": alert.payload,
                    }
                    for alert in self.v2x_alerts
                ],
            }
            self.v2x.publish_basic_safety_message(snapshot)
            self.live_publisher.publish(snapshot)

            self._render()

            self.elapsed += 0.5

            self.root.after(
                500,
                self.tick,
            )

        except Exception as error:

            self.diagnostic_label.config(
                text=(
                    "DIGITAL TWIN ERROR:\n"
                    f"{error}"
                ),
                fg=RED,
            )

            self.root.after(
                1000,
                self.tick,
            )

    # ========================================================
    # RENDER
    # ========================================================

    def _animate_v2x(self) -> None:
        """Animate the V2V field around the vehicle model."""
        self.v2x_phase = (self.v2x_phase + 2) % 20
        active = not self.hardware_mode or self.v2x.enabled or bool(self.v2x_alerts)
        for index, item in enumerate(self.v2x_wave_items):
            self.canvas.itemconfigure(
                item,
                state="normal" if active else "hidden",
                dashoffset=self.v2x_phase + index * 6,
            )
        self.canvas.itemconfigure(
            self.v2x_caption,
            text=(
                "V2V LINK · ACTIVE"
                if self.v2x.enabled or self.v2x_alerts
                else "V2V LINK · SIMULATION"
            ),
        )

    def _render(self) -> None:

        # ====================================================
        # ZONAL ECU STATUS
        # ====================================================

        for zone in ZONES:

            online = (
                self.cvc.zones[
                    zone
                ].status == "ONLINE"
            )

            self.canvas.itemconfigure(
                self.zone_items[
                    zone
                ],
                fill=(
                    "#244936"
                    if online
                    else "#552d35"
                ),
                outline=(
                    GREEN
                    if online
                    else RED
                ),
            )

        # ====================================================
        # NETWORK
        # ====================================================

        network_healthy = (
            self.cvc.network_status
            == "HEALTHY"
        )

        self.health_label.config(
            text=(
                f"● "
                f"{self.cvc.network_status}"
            ),
            fg=(
                GREEN
                if network_healthy
                else RED
            ),
        )

        status = "\n".join(
            f"{zone:<6} "
            f"{self.cvc.zones[zone].status}"
            for zone in ZONES
        )

        self.gateway_label.config(
            text=(
                f"ESP32 Gateway  "
                f"{self.cvc.gateway_status}"
                f"\n\n"
                f"{status}"
            )
        )

        for zone in ZONES:

            self.ecu_controls[
                zone
            ].set(
                (
                    zone not in
                    self.manual_faults
                )
                if not self.hardware_mode
                else (
                    self.cvc.zones[
                        zone
                    ].status == "ONLINE"
                )
            )

        # ====================================================
        # TELEMETRY
        # ====================================================

        front = self.cvc.zones[
            "FRONT"
        ].telemetry

        cabin = self.cvc.zones[
            "CABIN"
        ].telemetry

        rear = self.cvc.zones[
            "REAR"
        ].telemetry

        self._render_camera(rear)

        doors = cabin.get(
            "doors",
            {},
        )

        belts = cabin.get(
            "seatbelts",
            {},
        )

        # ====================================================
        # DOORS
        # ====================================================

        for key, item in (
            self.door_items.items()
        ):

            closed = (
                doors.get(key)
                == "CLOSED"
            )

            self.canvas.itemconfigure(
                item,
                fill=(
                    "#28563f"
                    if closed
                    else "#713c40"
                ),
                outline=(
                    GREEN
                    if closed
                    else RED
                ),
            )

        # ====================================================
        # BELTS
        # ====================================================

        for key, item in (
            self.belt_items.items()
        ):

            worn = (
                belts.get(key)
                == "WORN"
            )

            self.canvas.itemconfigure(
                item,
                fill=(
                    GREEN
                    if worn
                    else RED
                ),
            )

        # ====================================================
        # TELEMETRY TEXT
        # ====================================================

        # Categorize telemetry by the Zonal ECU that generated it.
        # Telemetry CAN IDs: FRONT 0x102, CABIN 0x202, REAR 0x302.
        driver_status = (
            "DETECTED"
            if cabin.get("driver_detected")
            else "NOT DETECTED"
        )

        doors_closed = sum(
            value == "CLOSED"
            for value in doors.values()
        )

        belts_worn = sum(
            value == "WORN"
            for value in belts.values()
        )

        self.telemetry_label.config(
            text=(
                "FRONT ZONAL ECU  |  TELEMETRY CAN ID 0x102\n"
                "────────────────────────────────────────\n"
                f"Speed             : {front.get('speed', '--')} km/h\n"
                f"Steering Angle    : {front.get('steering_angle', '--')}°\n"
                f"Obstacle Distance : {front.get('obstacle_distance', '--')} m\n"
                f"Obstacle Status   : {front.get('obstacle_status', '--')}\n\n"

                "CABIN ZONAL ECU  |  TELEMETRY CAN ID 0x202\n"
                "────────────────────────────────────────\n"
                f"Temperature       : {cabin.get('temperature', '--')} °C\n"
                f"Driver Detection  : {driver_status}\n"
                f"Doors Closed      : {doors_closed}/4\n"
                f"Seat Belts Worn   : {belts_worn}/4\n\n"

                "REAR ZONAL ECU   |  TELEMETRY CAN ID 0x302\n"
                "────────────────────────────────────────\n"
                f"Obstacle Distance : {rear.get('obstacle_distance', '--')} m\n"
                f"Obstacle Status   : {rear.get('obstacle_status', '--')}\n"
                f"Brake Status      : {rear.get('brake_status', '--')}\n"
                f"Rear Light        : {rear.get('rear_light_status', '--')}\n"
                f"Wheel RPM         : {rear.get('wheel_rpm', '--')}"
            )
        )

        # ====================================================
        # RECOVERY
        # ====================================================

        recovery_lines = []

        for zone in ZONES:

            state = self.cvc.zones[
                zone
            ]

            recovery_lines.append(
                f"{zone:<6} "
                f"{state.recovery_status:<10} "
                f"Attempts: "
                f"{state.recovery_attempts}"
            )

        recovery_active = any(
            self.cvc.zones[
                zone
            ].recovery_status
            in (
                "REQUESTED",
                "WAITING",
            )
            for zone in ZONES
        )

        recovery_success = any(
            self.cvc.zones[
                zone
            ].recovery_status
            == "RECOVERED"
            for zone in ZONES
        )

        if recovery_active:

            recovery_color = AMBER

        elif recovery_success:

            recovery_color = GREEN

        else:

            recovery_color = TEXT

        self.recovery_label.config(
            text="\n".join(
                recovery_lines
            ),
            fg=recovery_color,
        )

        # ====================================================
        # DIAGNOSTICS
        # ====================================================

        faults = (
            self.cvc.diagnostics()
        )

        if faults:

            diagnostic_text = (
                "ACTIVE DIAGNOSTICS\n"
                "──────────────────\n\n"
                + "\n".join(faults)
            )

            diagnostic_color = RED

        else:

            diagnostic_text = (
                "SYSTEM STATUS\n"
                "─────────────\n\n"
                "No active faults\n\n"
                "Vehicle network "
                "operating normally"
            )

            diagnostic_color = GREEN

        self.diagnostic_label.config(
            text=diagnostic_text,
            fg=diagnostic_color,
        )

        self._render_ml()

    # ========================================================
    # RENDER ML
    # ========================================================

    def _render_ml(self) -> None:

        condition = (
            self.ml_result.condition
        )

        if condition == "NORMAL":

            condition_color = GREEN

        elif condition == "WARNING":

            condition_color = AMBER

        else:

            condition_color = RED

        data = self.condition_data
        result = self.ml_result

        self.ml_label.config(
            text=(
                "ML HEALTH SUMMARY\n"
                "─────────────────\n"

                f"Condition    : "
                f"{result.condition}\n"

                f"Risk         : "
                f"{result.risk_score:.1f}%\n"

                f"Confidence   : "
                f"{result.confidence:.1f}%\n\n"

                f"Voltage      : "
                f"{data.voltage:.1f} V\n"

                f"Current      : "
                f"{data.current:.1f} A\n"

                f"Temperature  : "
                f"{data.temperature:.1f} °C\n"

                f"Vibration    : "
                f"{data.vibration:.1f}\n"

                f"RPM          : "
                f"{data.rpm:.0f}\n"

                f"Comm Health  : "
                f"{data.communication_health:.0f}%\n\n"

                f"V2X Alerts   : "
                f"{len(self.v2x_alerts)}\n\n"

                f"Recommendation:\n"
                f"{result.recommendation}"
            ),
            fg=condition_color,
        )


# ============================================================
# START APPLICATION
# ============================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description=(
            "Run the integrated SVA Digital Twin"
        )
    )

    parser.add_argument(
        "--port",
        help="ESP32 serial port",
    )

    parser.add_argument(
        "--baud",
        type=int,
        default=115200,
    )

    parser.add_argument(
        "--rear-camera",
        action="store_true",
        help="Enable OpenCV rear pedestrian detection in the desktop Digital Twin",
    )

    parser.add_argument(
        "--camera-index",
        type=int,
        default=0,
        help="OpenCV camera device index used with --rear-camera",
    )

    args = parser.parse_args()

    root = tk.Tk()

    DigitalTwin(
        root,
        args.port,
        args.baud,
        args.camera_index if args.rear_camera else None,
    )

    root.mainloop()