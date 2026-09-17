"""Console demo for the STM32 zonal ECU -> ESP32 CAN -> laptop CVC path."""

import time

from cvc_platform import CentralVehicleComputer
from esp32_gateway import ESP32Gateway, SimulatedCANBus
from zonal_ecu import ZonalECU


def main() -> None:
    bus = SimulatedCANBus()
    gateway = ESP32Gateway(bus)
    cvc = CentralVehicleComputer(gateway)
    ecus = [ZonalECU(zone) for zone in ("FRONT", "CABIN", "REAR")]

    print("Three-zone SVA platform simulation")
    print("STM32 ECUs -> CAN bus -> ESP32 gateway -> Central Vehicle Computer")

    started = time.monotonic()
    for _ in range(5):
        now = time.monotonic()
        elapsed = now - started
        for ecu in ecus:
            if ecu.zone != "REAR" or elapsed < 2:
                for frame in (ecu.heartbeat(elapsed), ecu.telemetry(elapsed)):
                    if frame:
                        gateway.send(frame)
        cvc.poll(now)
        print(
            " | ".join(
                [f"{zone}: {cvc.zones[zone].status}" for zone in cvc.zones]
            ),
            f"| Network: {cvc.network_status}",
        )
        time.sleep(1)

    for fault in cvc.diagnostics():
        print(f"FAULT {fault}")


if __name__ == "__main__":
    main()
