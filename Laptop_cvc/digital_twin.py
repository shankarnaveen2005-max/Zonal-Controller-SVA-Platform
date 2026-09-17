"""Live digital twin for the three-zone SVA platform."""

import tkinter as tk

from cvc_platform import CentralVehicleComputer
from esp32_gateway import ESP32Gateway, SimulatedCANBus
from zonal_ecu import ZonalECU


class DigitalTwin:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("SVA Central Vehicle Computer")
        self.root.geometry("760x520")

        self.bus = SimulatedCANBus()
        self.gateway = ESP32Gateway(self.bus)
        self.cvc = CentralVehicleComputer(self.gateway)
        self.ecus = [ZonalECU(zone) for zone in ("FRONT", "CABIN", "REAR")]
        self.started = 0.0

        tk.Label(
            root,
            text="ZONAL CONTROLLER-BASED SOFTWARE VEHICLE ARCHITECTURE",
            font=("Arial", 16, "bold"),
        ).pack(pady=15)
        self.state_label = self._section("VEHICLE STATE")
        self.network_label = self._section("ZONAL ECU NETWORK")
        self.health_label = self._section("NETWORK HEALTH")
        self.diagnostic_label = self._section("DIAGNOSTICS")
        self.tick()

    def _section(self, title: str) -> tk.Label:
        frame = tk.LabelFrame(self.root, text=title, font=("Arial", 11, "bold"))
        frame.pack(fill="x", padx=25, pady=6)
        label = tk.Label(frame, font=("Arial", 11), justify="left", anchor="w")
        label.pack(fill="x", padx=12, pady=8)
        return label

    def tick(self) -> None:
        elapsed = self.started
        for ecu in self.ecus:
            for frame in (ecu.heartbeat(elapsed), ecu.telemetry(elapsed)):
                if frame:
                    self.gateway.send(frame)
        self.cvc.poll(elapsed)
        self._render()
        self.started += 0.5
        self.root.after(500, self.tick)

    def _render(self) -> None:
        front = self.cvc.zones["FRONT"].telemetry
        cabin = self.cvc.zones["CABIN"].telemetry
        rear = self.cvc.zones["REAR"].telemetry
        self.state_label.config(
            text=(
                f"Speed: {front.get('speed_kph', '--')} km/h    "
                f"Front obstacle: {front.get('obstacle', '--')}\n"
                f"Cabin temperature: {cabin.get('temperature_c', '--')} °C    "
                f"Driver: {'DETECTED' if cabin.get('driver_detected') else 'NOT DETECTED'}\n"
                f"Rear obstacle: {rear.get('obstacle', '--')}    "
                f"Rear status: {rear.get('status', '--')}"
            )
        )
        self.network_label.config(
            text="\n".join(
                [f"{zone.title()} Zonal ECU: {self.cvc.zones[zone].status}" for zone in self.cvc.zones]
                + [f"ESP32 Gateway: {self.cvc.gateway_status}"]
            )
        )
        self.health_label.config(text=f"Overall vehicle network: {self.cvc.network_status}")
        faults = self.cvc.diagnostics()
        self.diagnostic_label.config(
            text="No active faults" if not faults else "\n".join(faults)
        )


if __name__ == "__main__":
    root = tk.Tk()
    DigitalTwin(root)
    root.mainloop()
