"""Graphical digital twin for simulation or a physical ESP32 gateway."""

import argparse
import tkinter as tk
from tkinter import ttk

from cvc_platform import CentralVehicleComputer, ZONES
from esp32_gateway import ESP32Gateway, SerialGatewayTransport, SimulatedGatewayTransport
from zonal_ecu import ZonalECU

BG = "#101820"
PANEL = "#1b2935"
TEXT = "#e8f1f5"
GREEN = "#27c281"
RED = "#ef6262"
AMBER = "#f3b33d"


class DigitalTwin:
    def __init__(self, root: tk.Tk, port: str | None = None, baudrate: int = 115200) -> None:
        self.root = root
        self.root.title("SVA Digital Twin | Central Vehicle Computer")
        self.root.geometry("1050x720")
        self.root.configure(bg=BG)

        transport = SerialGatewayTransport(port, baudrate) if port else SimulatedGatewayTransport()
        self.gateway = ESP32Gateway(transport)
        self.cvc = CentralVehicleComputer(self.gateway)
        self.ecus = {zone: ZonalECU(zone) for zone in ZONES} if not port else {}
        self.hardware_mode = port is not None
        self.elapsed = 0.0
        self.zone_items: dict[str, int] = {}
        self.door_items: dict[str, int] = {}
        self.belt_items: dict[str, int] = {}

        self._build_header()
        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True, padx=18, pady=8)
        self._build_vehicle_view(body)
        self._build_sidebar(body)
        self._build_diagnostics()
        self.tick()

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=22, pady=(15, 4))
        tk.Label(
            header, text="SOFTWARE-DEFINED VEHICLE", fg="#6dd5fa", bg=BG,
            font=("Arial", 22, "bold"),
        ).pack(anchor="w")
        tk.Label(
            header, text="ZONAL CONTROLLER-BASED ARCHITECTURE  •  DIGITAL TWIN",
            fg=TEXT, bg=BG, font=("Arial", 10),
        ).pack(anchor="w")

    def _build_vehicle_view(self, parent: tk.Frame) -> None:
        panel = tk.LabelFrame(
            parent, text="LIVE VEHICLE MODEL", fg=TEXT, bg=PANEL,
            font=("Arial", 11, "bold"), padx=12, pady=12,
        )
        panel.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.canvas = tk.Canvas(panel, width=640, height=390, bg="#15232d", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_text(320, 17, text="FRONT", fill="#8fa6b3", font=("Arial", 10, "bold"))
        self.canvas.create_text(320, 367, text="REAR", fill="#8fa6b3", font=("Arial", 10, "bold"))
        self._zone("FRONT", 205, 35, 435, 105, "0x101 / 0x102")
        self._zone("CABIN", 185, 112, 455, 285, "0x201 / 0x202")
        self._zone("REAR", 205, 292, 435, 347, "0x301 / 0x302")
        self._draw_car_details()

    def _draw_car_details(self) -> None:
        """Draw the top-view doors and four seats inside the cabin zone."""
        for side, x in (("left", 178), ("right", 462)):
            for position, y in (("front", 135), ("rear", 220)):
                key = f"{position}_{side}"
                self.door_items[key] = self.canvas.create_rectangle(
                    x, y, x + (10 if side == "left" else -10), y + 58,
                    fill="#28563f", outline=GREEN, width=2,
                )
        seats = {
            "driver": (245, 137), "front_passenger": (345, 137),
            "rear_left": (245, 220), "rear_right": (345, 220),
        }
        for key, (x, y) in seats.items():
            self.canvas.create_rectangle(x, y, x + 48, y + 55, fill="#344b59", outline="#91aab5")
            self.belt_items[key] = self.canvas.create_line(
                x + 8, y + 8, x + 40, y + 47, fill=GREEN, width=4,
            )
        self.canvas.create_text(320, 199, text="4-SEAT CABIN", fill="#b9ced6", font=("Arial", 9, "bold"))

    def _zone(self, zone: str, x1: int, y1: int, x2: int, y2: int, can_ids: str) -> None:
        item = self.canvas.create_rectangle(x1, y1, x2, y2, fill="#244936", outline=GREEN, width=2)
        self.zone_items[zone] = item
        self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2 - 7, text=f"{zone} ZONAL ECU",
                                fill=TEXT, font=("Arial", 14, "bold"))
        self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2 + 17, text=can_ids,
                                fill="#9fc0ce", font=("Arial", 9))

    def _build_sidebar(self, parent: tk.Frame) -> None:
        panel = tk.LabelFrame(
            parent, text="CVC / GATEWAY", fg=TEXT, bg=PANEL,
            font=("Arial", 11, "bold"), padx=12, pady=12, width=270,
        )
        panel.pack(side="right", fill="y")
        self.health_label = tk.Label(panel, fg=GREEN, bg=PANEL, font=("Arial", 15, "bold"))
        self.health_label.pack(pady=(4, 15))
        self.gateway_label = tk.Label(panel, fg=TEXT, bg=PANEL, justify="left", font=("Arial", 10))
        self.gateway_label.pack(anchor="w", pady=4)
        ttk.Separator(panel).pack(fill="x", pady=12)
        tk.Label(panel, text="CABIN CONTROLS", fg="#6dd5fa", bg=PANEL,
                 font=("Arial", 10, "bold")).pack(anchor="w")
        for label, action in (
            ("Toggle all doors", self.toggle_doors),
            ("Toggle all seat belts", self.toggle_seatbelts),
        ):
            ttk.Button(panel, text=label, command=action).pack(fill="x", pady=3)
        ttk.Separator(panel).pack(fill="x", pady=12)
        tk.Label(panel, text="FAULT INJECTION", fg="#f3b33d", bg=PANEL,
                 font=("Arial", 10, "bold")).pack(anchor="w")
        for zone in ZONES:
            ttk.Button(panel, text=f"Toggle {zone} ECU",
                       command=lambda selected=zone: self.toggle_ecu(selected)).pack(fill="x", pady=3)
        ttk.Button(panel, text="Toggle ESP32 Gateway",
                   command=self.toggle_gateway).pack(fill="x", pady=3)
        ttk.Button(panel, text="Clear faults / restore network",
                   command=self.restore_network).pack(fill="x", pady=(12, 3))

    def _build_diagnostics(self) -> None:
        panel = tk.LabelFrame(
            self.root, text="TELEMETRY AND DIAGNOSTICS", fg=TEXT, bg=PANEL,
            font=("Arial", 11, "bold"), padx=12, pady=8,
        )
        panel.pack(fill="x", padx=18, pady=(0, 15))
        self.telemetry_label = tk.Label(panel, fg=TEXT, bg=PANEL, justify="left",
                                        anchor="w", font=("Courier", 10))
        self.telemetry_label.pack(side="left", fill="x", expand=True)
        self.diagnostic_label = tk.Label(panel, fg=AMBER, bg=PANEL, justify="left",
                                         anchor="w", font=("Courier", 10))
        self.diagnostic_label.pack(side="right", fill="x", expand=True)

    def toggle_ecu(self, zone: str) -> None:
        if not self.hardware_mode:
            self.ecus[zone].online = not self.ecus[zone].online

    def toggle_gateway(self) -> None:
        if isinstance(self.gateway.transport, SimulatedGatewayTransport):
            self.gateway.transport.connected = not self.gateway.transport.connected

    def restore_network(self) -> None:
        if self.hardware_mode:
            return
        if isinstance(self.gateway.transport, SimulatedGatewayTransport):
            self.gateway.transport.connected = True
        for ecu in self.ecus.values():
            ecu.online = True

    def toggle_doors(self) -> None:
        if self.hardware_mode:
            return
        cabin = self.ecus["CABIN"].telemetry(self.elapsed)
        if cabin is None:
            return
        doors = cabin.payload["doors"]
        new_state = "OPEN" if all(state == "CLOSED" for state in doors.values()) else "CLOSED"
        self.ecus["CABIN"].door_state = new_state

    def toggle_seatbelts(self) -> None:
        if self.hardware_mode:
            return
        cabin = self.ecus["CABIN"].telemetry(self.elapsed)
        if cabin is None:
            return
        belts = cabin.payload["seatbelts"]
        new_state = "WORN" if all(state == "NOT WORN" for state in belts.values()) else "NOT WORN"
        self.ecus["CABIN"].belt_state = new_state

    def tick(self) -> None:
        if not self.hardware_mode:
            for ecu in self.ecus.values():
                for frame in (ecu.heartbeat(self.elapsed), ecu.telemetry(self.elapsed)):
                    if frame and self.gateway.connected:
                        self.gateway.send(frame)
            self.cvc.poll(self.elapsed)
        else:
            self.cvc.poll()
        self._render()
        self.elapsed += 0.5
        self.root.after(500, self.tick)

    def _render(self) -> None:
        for zone in ZONES:
            online = self.cvc.zones[zone].status == "ONLINE"
            self.canvas.itemconfigure(self.zone_items[zone], fill="#244936" if online else "#552d35",
                                      outline=GREEN if online else RED)
        self.health_label.config(
            text=f"● {self.cvc.network_status}",
            fg=GREEN if self.cvc.network_status == "HEALTHY" else RED,
        )
        status = "\n".join(f"{zone:<6} {self.cvc.zones[zone].status}" for zone in ZONES)
        self.gateway_label.config(text=f"ESP32 Gateway  {self.cvc.gateway_status}\n\n{status}")
        front = self.cvc.zones["FRONT"].telemetry
        cabin = self.cvc.zones["CABIN"].telemetry
        rear = self.cvc.zones["REAR"].telemetry
        doors = cabin.get("doors", {})
        belts = cabin.get("seatbelts", {})
        for key, item in self.door_items.items():
            closed = doors.get(key) == "CLOSED"
            self.canvas.itemconfigure(item, fill="#28563f" if closed else "#713c40",
                                      outline=GREEN if closed else RED)
        for key, item in self.belt_items.items():
            worn = belts.get(key) == "WORN"
            self.canvas.itemconfigure(item, fill=GREEN if worn else RED)
        self.telemetry_label.config(text=(
            f"Speed             {front.get('speed_kph', '--')} km/h\n"
            f"Cabin temperature {cabin.get('temperature_c', '--')} °C\n"
            f"Driver            {'DETECTED' if cabin.get('driver_detected') else '--'}\n"
            f"Front / rear      {front.get('obstacle', '--')} / {rear.get('obstacle', '--')}\n"
            f"Doors             {sum(value == 'CLOSED' for value in doors.values())}/4 CLOSED\n"
            f"Seat belts        {sum(value == 'WORN' for value in belts.values())}/4 WORN"
        ))
        faults = self.cvc.diagnostics()
        self.diagnostic_label.config(text="No active faults" if not faults else "\n".join(faults))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the SVA digital twin")
    parser.add_argument("--port", help="ESP32 serial port")
    parser.add_argument("--baud", type=int, default=115200)
    args = parser.parse_args()
    root = tk.Tk()
    DigitalTwin(root, args.port, args.baud)
    root.mainloop()
