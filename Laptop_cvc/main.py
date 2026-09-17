"""Console demo for simulation or a physical ESP32 CAN gateway."""

import argparse
import time

from cvc_platform import CentralVehicleComputer
from esp32_gateway import (
    ESP32Gateway,
    SerialGatewayTransport,
    SimulatedGatewayTransport,
)
from zonal_ecu import ZonalECU


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the laptop CVC")
    parser.add_argument("--port", help="ESP32 serial port, for example /dev/cu.usbserial-0001")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument(
        "--duration",
        type=float,
        default=5.0,
        help="simulation run time in seconds; ignored in hardware mode",
    )
    args = parser.parse_args()

    transport = (
        SerialGatewayTransport(args.port, args.baud)
        if args.port
        else SimulatedGatewayTransport()
    )
    gateway = ESP32Gateway(transport)
    cvc = CentralVehicleComputer(gateway)
    ecus = [ZonalECU(zone) for zone in ("FRONT", "CABIN", "REAR")] if not args.port else []

    print("Three-zone SVA CVC")
    print("STM32 ECUs -> CAN bus -> ESP32 gateway -> Central Vehicle Computer")

    started = time.monotonic()
    while args.port or time.monotonic() - started < args.duration:
        elapsed = time.monotonic() - started
        for ecu in ecus:
            for frame in (ecu.heartbeat(elapsed), ecu.telemetry(elapsed)):
                if frame:
                    gateway.send(frame)
        cvc.poll()
        print(
            " | ".join(
                [f"{zone}: {cvc.zones[zone].status}" for zone in cvc.zones]
            ),
            f"| Network: {cvc.network_status}",
        )
        time.sleep(1)

    if not args.port:
        for fault in cvc.diagnostics():
            print(f"FAULT {fault}")


if __name__ == "__main__":
    main()
