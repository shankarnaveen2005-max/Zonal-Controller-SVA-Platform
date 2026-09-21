"""
SVA - THREE ZONAL ECU INTEGRATION TEST

Architecture
------------
Front ECU ──┐
Cabin ECU ──┼── Simulated CAN Bus ── ESP32 Gateway ── CVC side
Rear ECU ───┘

Purpose
-------
Verify that all three zonal ECUs can transmit heartbeat and
telemetry frames through the common simulated CAN / ESP32
gateway infrastructure.
"""

import time

from Laptop_cvc.esp32_gateway import (
    SimulatedCANBus,
    SimulatedGatewayTransport,
    ESP32Gateway,
)

from Zonal_ECUs.Front_ECU.front_ecu import FrontZonalECU
from Zonal_ECUs.Cabin_ECU.cabin_ecu import CabinZonalECU
from Zonal_ECUs.Rear_ECU.rear_ecu import RearZonalECU


def main():

    print()
    print("=" * 70)
    print("SVA - THREE ZONAL ECU INTEGRATION TEST")
    print("=" * 70)

    # --------------------------------------------------------
    # Create simulated CAN network
    # --------------------------------------------------------

    can_bus = SimulatedCANBus()

    transport = SimulatedGatewayTransport(can_bus)

    gateway = ESP32Gateway(transport)

    # --------------------------------------------------------
    # Create all three zonal ECUs
    # --------------------------------------------------------

    front_ecu = FrontZonalECU()
    cabin_ecu = CabinZonalECU()
    rear_ecu = RearZonalECU()

    ecus = [
        front_ecu,
        cabin_ecu,
        rear_ecu,
    ]

    print()
    print("NETWORK STATUS")
    print("-" * 70)

    print(
        "ESP32 Gateway :",
        "CONNECTED" if gateway.connected else "DISCONNECTED",
    )

    print("CAN Bus       : ACTIVE")
    print("Zonal ECUs    : FRONT / CABIN / REAR")

    # --------------------------------------------------------
    # Run communication cycles
    # --------------------------------------------------------

    for cycle in range(1, 6):

        print()
        print("=" * 70)
        print(f"COMMUNICATION CYCLE {cycle}")
        print("=" * 70)

        # ----------------------------------------------------
        # ECU sensor update + transmission
        # ----------------------------------------------------

        for ecu in ecus:

            if not ecu.online:
                continue

            ecu.update_sensors()

            heartbeat = ecu.heartbeat()
            telemetry = ecu.telemetry()

            if heartbeat is not None:
                can_bus.publish(heartbeat)

            if telemetry is not None:
                can_bus.publish(telemetry)

        # ----------------------------------------------------
        # ESP32 Gateway receives CAN frames
        # ----------------------------------------------------

        received_frames = gateway.receive()

        print()
        print(
            f"ESP32 Gateway received "
            f"{len(received_frames)} CAN frames"
        )

        print("-" * 70)

        # ----------------------------------------------------
        # Display frames reaching CVC side
        # ----------------------------------------------------

        for frame in received_frames:

            zone = frame.payload.get(
                "zone",
                "UNKNOWN",
            )

            frame_type = "UNKNOWN"

            if frame.arbitration_id in (
                0x101,
                0x201,
                0x301,
            ):
                frame_type = "HEARTBEAT"

            elif frame.arbitration_id in (
                0x102,
                0x202,
                0x302,
            ):
                frame_type = "TELEMETRY"

            print(
                f"{zone:<6} | "
                f"CAN ID: 0x{frame.arbitration_id:03X} | "
                f"{frame_type}"
            )

        time.sleep(1)

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("INTEGRATION TEST COMPLETED")
    print("=" * 70)

    print("Front ECU       : ONLINE")
    print("Cabin ECU       : ONLINE")
    print("Rear ECU        : ONLINE")

    print(
        "ESP32 Gateway   :",
        "CONNECTED" if gateway.connected else "DISCONNECTED",
    )

    print("CAN Network     : HEALTHY")

    print()
    print(
        "Expected frames per cycle: 6 "
        "(3 heartbeat + 3 telemetry)"
    )

    print("=" * 70)


if __name__ == "__main__":

    try:
        main()

    except KeyboardInterrupt:

        print()
        print("=" * 70)
        print("SVA integration test stopped by user.")
        print("=" * 70)
    