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
"""

import argparse
import tkinter as tk
from tkinter import ttk

from can_protocol import recovery_frame
from cvc_platform import CentralVehicleComputer, ZONES
from data_logging import DataLogger
from esp32_gateway import (
    ESP32Gateway,
    SerialGatewayTransport,
    SimulatedGatewayTransport,
)
from zonal_ecu import ZonalECU

from predictive_maintenance import (
    PredictiveMaintenance,
    ConditionData,
)


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


# ============================================================
# DIGITAL TWIN
# ============================================================

class DigitalTwin:

    def __init__(
        self,
        root: tk.Tk,
        port: str | None = None,
        baudrate: int = 115200,
    ) -> None:

        self.root = root

        self.root.title(
            "SVA Digital Twin | Central Vehicle Computer"
        )

        self.root.geometry("1250x850")
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
                zone: ZonalECU(zone)
                for zone in ZONES
            }
            if not port
            else {}
        )

        self.hardware_mode = port is not None

        self.elapsed = 0.0

        # ====================================================
        # AUTONOMOUS RECOVERY TRACKING
        # ====================================================

        self.recovery_requested = {
            zone: False
            for zone in ZONES
        }

        # ====================================================
        # ML PREDICTIVE MAINTENANCE
        # ====================================================

        self.predictive_system = PredictiveMaintenance()

        print("\nTraining predictive maintenance model...")

        accuracy = self.predictive_system.train(
            samples_per_class=500
        )

        print(
            f"Predictive maintenance model ready. "
            f"Test accuracy: {accuracy * 100:.2f}%\n"
        )

        # ====================================================
        # SIMULATED CONDITION VALUES
        # ====================================================

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
        # GUI OBJECT STORAGE
        # ====================================================

        self.zone_items: dict[str, int] = {}
        self.door_items: dict[str, int] = {}
        self.belt_items: dict[str, int] = {}

        # ====================================================
        # BUILD GUI
        # ====================================================

        self._build_header()

        body = tk.Frame(
            root,
            bg=BG,
        )

        body.pack(
            fill="both",
            expand=True,
            padx=18,
            pady=8,
        )

        self._build_vehicle_view(body)
        self._build_sidebar(body)
        self._build_bottom_panel()

        # Start application
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
            pady=(15, 4),
        )

        tk.Label(
            header,
            text="SOFTWARE VEHICLE ARCHITECTURE",
            fg=BLUE,
            bg=BG,
            font=("Arial", 22, "bold"),
        ).pack(anchor="w")

        tk.Label(
            header,
            text=(
                "ZONAL CONTROLLER-BASED ARCHITECTURE"
                "  •  DIGITAL TWIN"
                "  •  ML PREDICTIVE MAINTENANCE"
            ),
            fg=TEXT,
            bg=BG,
            font=("Arial", 10),
        ).pack(anchor="w")


    # ========================================================
    # VEHICLE VIEW
    # ========================================================

    def _build_vehicle_view(
        self,
        parent: tk.Frame,
    ) -> None:

        panel = tk.LabelFrame(
            parent,
            text="LIVE VEHICLE MODEL",
            fg=TEXT,
            bg=PANEL,
            font=("Arial", 11, "bold"),
            padx=12,
            pady=12,
        )

        panel.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(0, 10),
        )

        self.canvas = tk.Canvas(
            panel,
            width=720,
            height=600,
            bg="#15232d",
            highlightthickness=0,
        )

        self.canvas.pack(
            fill="both",
            expand=True,
        )

        self.canvas.create_text(360, 18, text="FRONT OF VEHICLE",
                                fill="#b8cbd3", font=("Arial", 10, "bold"))
        self.canvas.create_text(360, 578, text="REAR OF VEHICLE",
                                fill="#b8cbd3", font=("Arial", 10, "bold"))
        self._rounded_rectangle(175, 32, 545, 565, 46, fill="#0d151b", outline="#6e8792", width=3)

        self._zone(
            "FRONT",
            210,
            52,
            510,
            145,
            "0x101 / 0x102",
        )

        self._zone(
            "CABIN",
            195,
            158,
            525,
            430,
            "0x201 / 0x202",
        )

        self._zone(
            "REAR",
            210,
            443,
            510,
            545,
            "0x301 / 0x302",
        )

        self._draw_car_details()


    # ========================================================
    # VEHICLE DETAILS
    # ========================================================

    def _draw_car_details(self) -> None:
        """Draw separated doors and seats inside the larger top-view body."""
        for side, x in (
            ("left", 183),
            ("right", 537),
        ):

            for position, y in (
                ("front", 185),
                ("rear", 315),
            ):

                key = f"{position}_{side}"

                self.door_items[key] = (
                    self.canvas.create_rectangle(
                        x,
                        y,
                        x + (
                            12
                            if side == "left"
                            else -12
                        ),
                        y + 100,
                        fill="#28563f",
                        outline=GREEN,
                        width=3,
                    )
                )

        seats = {
            "driver": (265, 190),
            "front_passenger": (375, 190),
            "rear_left": (265, 315),
            "rear_right": (375, 315),
        }

        for key, (x, y) in seats.items():

            self.canvas.create_rectangle(
                x,
                y,
                x + 70,
                y + 85,
                fill="#344b59",
                outline="#b3c5cc",
                width=2,
            )

            self.belt_items[key] = (
                self.canvas.create_line(
                    x + 12,
                    y + 12,
                    x + 58,
                    y + 72,
                    fill=GREEN,
                    width=5,
                )
            )

        self.canvas.create_text(
            320,
            300,
            text="CABIN • 4 SEATS",
            fill="#d2e0e5",
            font=("Arial", 10, "bold"),
        )
        self.canvas.create_text(360, 470, text="Rear zone sensor / actuator area",
                                fill="#b8cbd3", font=("Arial", 9))

    def _rounded_rectangle(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        radius: int,
        **options: object,
    ) -> None:
        """Draw a rounded canvas rectangle from arcs and straight edges."""
        self.canvas.create_arc(x1, y1, x1 + 2 * radius, y1 + 2 * radius,
                               start=90, extent=90, style="pieslice", **options)
        self.canvas.create_arc(x2 - 2 * radius, y1, x2, y1 + 2 * radius,
                               start=0, extent=90, style="pieslice", **options)
        self.canvas.create_arc(x1, y2 - 2 * radius, x1 + 2 * radius, y2,
                               start=180, extent=90, style="pieslice", **options)
        self.canvas.create_arc(x2 - 2 * radius, y2 - 2 * radius, x2, y2,
                               start=270, extent=90, style="pieslice", **options)
        self.canvas.create_rectangle(x1 + radius, y1, x2 - radius, y2, **options)
        self.canvas.create_rectangle(x1, y1 + radius, x2, y2 - radius, **options)


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

        item = self.canvas.create_rectangle(
            x1,
            y1,
            x2,
            y2,
            fill="#244936",
            outline=GREEN,
            width=2,
        )

        self.zone_items[zone] = item

        self.canvas.create_text(
            (x1 + x2) / 2,
            (y1 + y2) / 2 - 7,
            text=f"{zone} ZONAL ECU",
            fill=TEXT,
            font=("Arial", 14, "bold"),
        )

        self.canvas.create_text(
            (x1 + x2) / 2,
            (y1 + y2) / 2 + 17,
            text=can_ids,
            fill="#9fc0ce",
            font=("Arial", 9),
        )


    # ========================================================
    # SIDEBAR
    # ========================================================

    def _build_sidebar(
        self,
        parent: tk.Frame,
    ) -> None:

        panel = tk.LabelFrame(
            parent,
            text="CVC / ESP32 GATEWAY",
            fg=TEXT,
            bg=PANEL,
            font=("Arial", 11, "bold"),
            padx=12,
            pady=12,
            width=320,
        )

        panel.pack(
            side="right",
            fill="y",
        )

        # ====================================================
        # NETWORK HEALTH
        # ====================================================

        self.health_label = tk.Label(
            panel,
            text="● STARTING",
            fg=AMBER,
            bg=PANEL,
            font=("Arial", 15, "bold"),
        )

        self.health_label.pack(
            pady=(4, 10)
        )

        self.gateway_label = tk.Label(
            panel,
            fg=TEXT,
            bg=PANEL,
            justify="left",
            font=("Arial", 10),
        )

        self.gateway_label.pack(
            anchor="w",
            pady=4,
        )

        # ====================================================
        # SELF-HEALING
        # ====================================================

        ttk.Separator(
            panel
        ).pack(
            fill="x",
            pady=8,
        )

        tk.Label(
            panel,
            text="SELF-HEALING / RECOVERY",
            fg=BLUE,
            bg=PANEL,
            font=("Arial", 10, "bold"),
        ).pack(anchor="w")

        self.recovery_label = tk.Label(
            panel,
            text=(
                "FRONT  IDLE\n"
                "CABIN  IDLE\n"
                "REAR   IDLE"
            ),
            fg=TEXT,
            bg=PANEL,
            justify="left",
            font=("Courier", 9),
        )

        self.recovery_label.pack(
            anchor="w",
            pady=(5, 6),
        )

        # ====================================================
        # CABIN CONTROLS
        # ====================================================

        ttk.Separator(
            panel
        ).pack(
            fill="x",
            pady=8,
        )

        tk.Label(
            panel,
            text="CABIN CONTROLS",
            fg=BLUE,
            bg=PANEL,
            font=("Arial", 10, "bold"),
        ).pack(anchor="w")

        ttk.Button(
            panel,
            text="Toggle all doors",
            command=self.toggle_doors,
        ).pack(
            fill="x",
            pady=2,
        )

        ttk.Button(
            panel,
            text="Toggle all seat belts",
            command=self.toggle_seatbelts,
        ).pack(
            fill="x",
            pady=2,
        )

        # ====================================================
        # FAULT INJECTION
        # ====================================================

        ttk.Separator(
            panel
        ).pack(
            fill="x",
            pady=8,
        )

        tk.Label(
            panel,
            text="FAULT INJECTION",
            fg=AMBER,
            bg=PANEL,
            font=("Arial", 10, "bold"),
        ).pack(anchor="w")

        for zone in ZONES:

            ttk.Button(
                panel,
                text=f"Toggle {zone} ECU",
                command=lambda selected=zone:
                self.toggle_ecu(selected),
            ).pack(
                fill="x",
                pady=2,
            )

        ttk.Button(
            panel,
            text="Toggle ESP32 Gateway",
            command=self.toggle_gateway,
        ).pack(
            fill="x",
            pady=2,
        )

        ttk.Button(
            panel,
            text="Clear faults / restore network",
            command=self.restore_network,
        ).pack(
            fill="x",
            pady=(6, 2),
        )

        # ====================================================
        # ML PREDICTIVE MAINTENANCE CONTROLS
        # ====================================================

        ttk.Separator(
            panel
        ).pack(
            fill="x",
            pady=8,
        )

        tk.Label(
            panel,
            text="ML CONDITION SIMULATION",
            fg=BLUE,
            bg=PANEL,
            font=("Arial", 10, "bold"),
        ).pack(anchor="w")

        ttk.Button(
            panel,
            text="Simulate Degradation",
            command=self.simulate_degradation,
        ).pack(
            fill="x",
            pady=2,
        )

        ttk.Button(
            panel,
            text="Reset Vehicle Condition",
            command=self.reset_condition,
        ).pack(
            fill="x",
            pady=2,
        )

        ttk.Button(
            panel,
            text="Run ML Prediction",
            command=self.run_ml_prediction,
        ).pack(
            fill="x",
            pady=2,
        )


    # ========================================================
    # BOTTOM PANEL
    # ========================================================

    def _build_bottom_panel(self) -> None:

        panel = tk.Frame(
            self.root,
            bg=BG,
        )

        panel.pack(
            fill="x",
            padx=18,
            pady=(0, 15),
        )

        # ====================================================
        # TELEMETRY
        # ====================================================

        telemetry_panel = tk.LabelFrame(
            panel,
            text="VEHICLE TELEMETRY",
            fg=TEXT,
            bg=PANEL,
            font=("Arial", 11, "bold"),
            padx=12,
            pady=8,
        )

        telemetry_panel.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(0, 5),
        )

        self.telemetry_label = tk.Label(
            telemetry_panel,
            fg=TEXT,
            bg=PANEL,
            justify="left",
            anchor="w",
            font=("Courier", 9),
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
            font=("Arial", 11, "bold"),
            padx=12,
            pady=8,
        )

        diagnostic_panel.pack(
            side="left",
            fill="both",
            expand=True,
            padx=5,
        )

        self.diagnostic_label = tk.Label(
            diagnostic_panel,
            fg=GREEN,
            bg=PANEL,
            justify="left",
            anchor="w",
            font=("Courier", 9),
            wraplength=350,
        )

        self.diagnostic_label.pack(
            fill="both",
            expand=True,
        )

        # ====================================================
        # ML PREDICTIVE MAINTENANCE
        # ====================================================

        ml_panel = tk.LabelFrame(
            panel,
            text="ML PREDICTIVE MAINTENANCE",
            fg=TEXT,
            bg=PANEL,
            font=("Arial", 11, "bold"),
            padx=12,
            pady=8,
        )

        ml_panel.pack(
            side="right",
            fill="both",
            expand=True,
            padx=(5, 0),
        )

        self.ml_label = tk.Label(
            ml_panel,
            fg=GREEN,
            bg=PANEL,
            justify="left",
            anchor="w",
            font=("Courier", 9),
            wraplength=370,
        )

        self.ml_label.pack(
            fill="both",
            expand=True,
        )


    # ========================================================
    # ECU FAULT INJECTION
    # ========================================================

    def toggle_ecu(
        self,
        zone: str,
    ) -> None:

        if self.hardware_mode:
            return

        ecu = self.ecus[zone]

        ecu.online = not ecu.online

        if ecu.online:

            self.recovery_requested[zone] = False


    # ========================================================
    # GATEWAY FAULT INJECTION
    # ========================================================

    def toggle_gateway(self) -> None:

        if isinstance(
            self.gateway.transport,
            SimulatedGatewayTransport,
        ):

            self.gateway.transport.connected = (
                not self.gateway.transport.connected
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

            self.recovery_requested[zone] = False

            state = self.cvc.zones[zone]

            state.recovery_status = "IDLE"
            state.recovery_attempts = 0


    # ========================================================
    # DOOR CONTROL
    # ========================================================

    def toggle_doors(self) -> None:

        if self.hardware_mode:
            return

        cabin = self.ecus["CABIN"].telemetry(
            self.elapsed
        )

        if cabin is None:
            return

        doors = cabin.payload["doors"]

        new_state = (
            "OPEN"
            if all(
                state == "CLOSED"
                for state in doors.values()
            )
            else "CLOSED"
        )

        self.ecus["CABIN"].door_state = (
            new_state
        )


    # ========================================================
    # SEAT BELT CONTROL
    # ========================================================

    def toggle_seatbelts(self) -> None:

        if self.hardware_mode:
            return

        cabin = self.ecus["CABIN"].telemetry(
            self.elapsed
        )

        if cabin is None:
            return

        belts = cabin.payload["seatbelts"]

        new_state = (
            "WORN"
            if all(
                state == "NOT WORN"
                for state in belts.values()
            )
            else "NOT WORN"
        )

        self.ecus["CABIN"].belt_state = (
            new_state
        )


    # ========================================================
    # ML DEGRADATION SIMULATION
    # ========================================================

    def simulate_degradation(self) -> None:

        if self.hardware_mode:
            return

        self.degradation_level += 1

        # ----------------------------------------------------
        # LEVEL 1 - MILD DEGRADATION
        # ----------------------------------------------------

        if self.degradation_level == 1:

            self.condition_data = ConditionData(
                voltage=12.0,
                current=8.0,
                temperature=66.0,
                vibration=3.7,
                rpm=3600,
                communication_health=88.0,
            )

        # ----------------------------------------------------
        # LEVEL 2 - WARNING CONDITION
        # ----------------------------------------------------

        elif self.degradation_level == 2:

            self.condition_data = ConditionData(
                voltage=11.7,
                current=9.2,
                temperature=75.0,
                vibration=4.6,
                rpm=4200,
                communication_health=78.0,
            )

        # ----------------------------------------------------
        # LEVEL 3+ - CRITICAL CONDITION
        # ----------------------------------------------------

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
    # RESET ML CONDITION
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
    # RUN ML PREDICTION
    # ========================================================

    def run_ml_prediction(self) -> None:

        self.ml_result = (
            self.predictive_system.predict(
                self.condition_data
            )
        )

        self._render_ml()


    # ========================================================
    # AUTONOMOUS SELF-HEALING
    # ========================================================

    def _automatic_recovery(self) -> None:

        if self.hardware_mode:
            return

        if not self.gateway.connected:
            return

        for zone in ZONES:

            state = self.cvc.zones[zone]

            # CVC confirmed loss of heartbeat
            if (
                state.status == "OFFLINE"
                and not self.recovery_requested[zone]
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

            # Recovery verified by heartbeat
            if (
                self.recovery_requested[zone]
                and state.recovery_status
                == "RECOVERED"
            ):

                self.recovery_requested[
                    zone
                ] = False


    # ========================================================
    # MAIN DIGITAL TWIN LOOP
    # ========================================================

    def tick(self) -> None:

        try:

            # =================================================
            # SIMULATION MODE
            # =================================================

            if not self.hardware_mode:

                for ecu in self.ecus.values():

                    heartbeat = ecu.heartbeat(
                        self.elapsed
                    )

                    telemetry = ecu.telemetry(
                        self.elapsed
                    )

                    for frame in (
                        heartbeat,
                        telemetry,
                    ):

                        if (
                            frame
                            and self.gateway.connected
                        ):

                            self.gateway.send(
                                frame
                            )

                self.cvc.poll(
                    self.elapsed
                )

                self._automatic_recovery()

            # =================================================
            # HARDWARE MODE
            # =================================================

            else:

                self.cvc.poll()

            # =================================================
            # UPDATE COMMUNICATION HEALTH FOR ML
            # =================================================

            online_count = sum(
                self.cvc.zones[zone].status
                == "ONLINE"
                for zone in ZONES
            )

            network_health = (
                online_count / len(ZONES)
            ) * 100.0

            if not self.gateway.connected:
                network_health = 0.0

            # Preserve degradation simulation if it is worse
            # than the current network value.
            communication_health = min(
                self.condition_data.communication_health,
                network_health,
            )

            self.condition_data = ConditionData(
                voltage=self.condition_data.voltage,
                current=self.condition_data.current,
                temperature=self.condition_data.temperature,
                vibration=self.condition_data.vibration,
                rpm=self.condition_data.rpm,
                communication_health=communication_health,
            )

            # =================================================
            # LIVE ML PREDICTION
            # =================================================

            self.ml_result = (
                self.predictive_system.predict(
                    self.condition_data
                )
            )

            # =================================================
            # DATA LOGGING
            # =================================================

            self.logger.log(
                self.cvc
            )

            # =================================================
            # RENDER DIGITAL TWIN
            # =================================================

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
    # RENDER COMPLETE DIGITAL TWIN
    # ========================================================

    def _render(self) -> None:

        # ====================================================
        # ZONAL ECU STATUS
        # ====================================================

        for zone in ZONES:

            online = (
                self.cvc.zones[
                    zone
                ].status
                == "ONLINE"
            )

            self.canvas.itemconfigure(
                self.zone_items[zone],
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
        # NETWORK HEALTH
        # ====================================================

        network_healthy = (
            self.cvc.network_status
            == "HEALTHY"
        )

        self.health_label.config(
            text=(
                f"● {self.cvc.network_status}"
            ),
            fg=(
                GREEN
                if network_healthy
                else RED
            ),
        )

        # ====================================================
        # GATEWAY + ECU STATUS
        # ====================================================

        status = "\n".join(
            f"{zone:<6} "
            f"{self.cvc.zones[zone].status}"
            for zone in ZONES
        )

        self.gateway_label.config(
            text=(
                f"ESP32 Gateway  "
                f"{self.cvc.gateway_status}"
                f"\n\n{status}"
            )
        )

        # ====================================================
        # TELEMETRY
        # ====================================================

        front = (
            self.cvc.zones[
                "FRONT"
            ].telemetry
        )

        cabin = (
            self.cvc.zones[
                "CABIN"
            ].telemetry
        )

        rear = (
            self.cvc.zones[
                "REAR"
            ].telemetry
        )

        doors = cabin.get(
            "doors",
            {},
        )

        belts = cabin.get(
            "seatbelts",
            {},
        )

        # ====================================================
        # DOOR VISUALIZATION
        # ====================================================

        for key, item in self.door_items.items():

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
        # SEAT BELT VISUALIZATION
        # ====================================================

        for key, item in self.belt_items.items():

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
        # TELEMETRY DISPLAY
        # ====================================================

        self.telemetry_label.config(
            text=(
                f"Speed             "
                f"{front.get('speed_kph', '--')} km/h\n"

                f"Cabin temperature "
                f"{cabin.get('temperature_c', '--')} °C\n"

                f"Driver            "
                f"{'DETECTED' if cabin.get('driver_detected') else '--'}\n"

                f"Front obstacle    "
                f"{front.get('obstacle', '--')}\n"

                f"Rear obstacle     "
                f"{rear.get('obstacle', '--')}\n"

                f"Doors             "
                f"{sum(value == 'CLOSED' for value in doors.values())}"
                f"/4 CLOSED\n"

                f"Seat belts        "
                f"{sum(value == 'WORN' for value in belts.values())}"
                f"/4 WORN"
            )
        )

        # ====================================================
        # SELF-HEALING STATUS
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

        faults = self.cvc.diagnostics()

        if faults:

            diagnostic_text = (
                "ACTIVE DIAGNOSTICS\n\n"
                + "\n".join(faults)
            )

            diagnostic_color = RED

        else:

            diagnostic_text = (
                "No active faults\n\n"
                "Vehicle network operating normally"
            )

            diagnostic_color = GREEN

        self.diagnostic_label.config(
            text=diagnostic_text,
            fg=diagnostic_color,
        )

        # ====================================================
        # ML DISPLAY
        # ====================================================

        self._render_ml()


    # ========================================================
    # RENDER ML PREDICTIVE MAINTENANCE
    # ========================================================

    def _render_ml(self) -> None:

        condition = self.ml_result.condition

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

    args = parser.parse_args()

    root = tk.Tk()

    DigitalTwin(
        root,
        args.port,
        args.baud,
    )

    root.mainloop()