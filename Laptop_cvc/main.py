"""
Integrated SVA Central Vehicle Computer

Architecture:
Front Zonal ECU ──┐
Cabin Zonal ECU ──┼── CAN Bus ── ESP32 Gateway ── Laptop CVC
Rear Zonal ECU ───┘
"""

import argparse
import os
import sys
import time


# ============================================================
# PROJECT PATH
# ============================================================

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ============================================================
# CVC IMPORTS
# ============================================================

from can_protocol import recovery_frame
from cvc_platform import CentralVehicleComputer
from data_logging import DataLogger
from live_data import MqttStatePublisher, snapshot_from_cvc
from v2x import V2XService

from esp32_gateway import (
    DirectCANTransport,
    ESP32Gateway,
    SerialGatewayTransport,
    SimulatedGatewayTransport,
)


# ============================================================
# DEDICATED ZONAL ECU IMPORTS
# ============================================================

from Zonal_ECUs.Front_ECU.front_ecu import FrontZonalECU
from Zonal_ECUs.Cabin_ECU.cabin_ecu import CabinZonalECU
from Zonal_ECUs.Rear_ECU.rear_ecu import RearZonalECU


# ============================================================
# MAIN APPLICATION
# ============================================================

def main() -> None:

    # ========================================================
    # COMMAND-LINE CONFIGURATION
    # ========================================================

    parser = argparse.ArgumentParser(
        description="Run the integrated SVA Laptop CVC"
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
        "--can-channel",
        help="Direct CAN interface name, for example can0 or vcan0",
    )

    parser.add_argument(
        "--can-bustype",
        default="socketcan",
        help="python-can bus type for direct CAN hardware mode",
    )

    parser.add_argument(
        "--can-bitrate",
        type=int,
        default=500000,
        help="CAN bitrate for direct CAN hardware mode",
    )

    parser.add_argument(
        "--duration",
        type=float,
        default=12.0,
        help=(
            "Simulation runtime in seconds; "
            "ignored in hardware mode"
        ),
    )

    args = parser.parse_args()


    # ========================================================
    # ESP32 GATEWAY
    # ========================================================

    if args.can_channel:

        transport = DirectCANTransport(
            channel=args.can_channel,
            bustype=args.can_bustype,
            bitrate=args.can_bitrate,
        )

    elif args.port:

        transport = SerialGatewayTransport(
            args.port,
            args.baud,
        )

    else:

        transport = SimulatedGatewayTransport()

    gateway = ESP32Gateway(
        transport
    )


    # ========================================================
    # CENTRAL VEHICLE COMPUTER
    # ========================================================

    cvc = CentralVehicleComputer(
        gateway
    )


    # ========================================================
    # DATA LOGGER
    # ========================================================

    logger = DataLogger()
    state_publisher = MqttStatePublisher()
    v2x = V2XService()


    # ========================================================
    # DEDICATED ZONAL ECUs
    # ========================================================

    if not args.port and not args.can_channel:

        front_ecu = FrontZonalECU()
        cabin_ecu = CabinZonalECU()
        rear_ecu = RearZonalECU()

        ecus = [
            front_ecu,
            cabin_ecu,
            rear_ecu,
        ]

    else:

        ecus = []


    # ========================================================
    # STARTUP DISPLAY
    # ========================================================

    print()
    print("=" * 65)
    print("       INTEGRATED THREE-ZONE SVA CVC PLATFORM")
    print("=" * 65)

    print(
        "Zonal ECUs -> CAN Bus -> ESP32 Gateway -> Laptop CVC"
    )

    print(
        f"ESP32 Gateway      : {cvc.gateway_status}"
    )

    print(
        "Data Logging       : ENABLED"
    )

    if args.can_channel:

        print(
            "Operating Mode     : HARDWARE CAN"
        )

    elif args.port:

        print(
            "Operating Mode     : HARDWARE ESP32"
        )

    else:

        print(
            "Operating Mode     : SIMULATION"
        )

        print(
            "Front Zonal ECU    : LOADED"
        )

        print(
            "Cabin Zonal ECU    : LOADED"
        )

        print(
            "Rear Zonal ECU     : LOADED"
        )

    print("=" * 65)
    print()


    # ========================================================
    # SIMULATION CONTROL
    # ========================================================

    started = time.monotonic()

    fault_injected = False
    recovery_requested = False
    recovery_completed = False


    # ========================================================
    # MAIN LOOP
    # ========================================================

    while (
        args.port
        or args.can_channel
        or time.monotonic() - started < args.duration
    ):

        elapsed = (
            time.monotonic()
            - started
        )


        # ====================================================
        # SIMULATION MODE
        # ====================================================

        if not args.port and not args.can_channel:

            # ------------------------------------------------
            # REAR ECU FAULT INJECTION
            # ------------------------------------------------

            if (
                elapsed >= 3
                and not fault_injected
            ):

                rear_ecu.inject_fault()

                fault_injected = True

                print()
                print(
                    "[FAULT INJECTION] "
                    "Rear Zonal ECU communication stopped."
                )
                print()


            # ------------------------------------------------
            # ZONAL ECU SENSOR UPDATE + CAN TRANSMISSION
            # ------------------------------------------------

            for ecu in ecus:

                if not ecu.online:
                    continue

                # Update zone-specific simulated sensors
                ecu.update_sensors()

                # Create heartbeat frame
                heartbeat_frame = (
                    ecu.heartbeat()
                )

                # Create telemetry frame
                telemetry_frame = (
                    ecu.telemetry()
                )

                # Send heartbeat to gateway
                if heartbeat_frame is not None:

                    gateway.send(
                        heartbeat_frame
                    )

                # Send telemetry to gateway
                if telemetry_frame is not None:

                    gateway.send(
                        telemetry_frame
                    )


        # ====================================================
        # CENTRAL VEHICLE COMPUTER PROCESSING
        # ====================================================

        cvc.poll()

        v2x_alerts = v2x.receive_alerts()
        snapshot = snapshot_from_cvc(cvc, v2x_alerts)
        state_publisher.publish(snapshot)
        v2x.publish_basic_safety_message(snapshot)

        for alert in v2x_alerts:
            print(
                f"[V2X] {alert.message_type} received from "
                f"{alert.station_id}"
            )


        # ====================================================
        # DATA LOGGING
        # ====================================================

        logger.log(
            cvc
        )


        # ====================================================
        # DISPLAY ZONAL ECU STATUS
        # ====================================================

        zone_status = " | ".join(
            [
                f"{zone}: {cvc.zones[zone].status}"
                for zone in cvc.zones
            ]
        )

        print(
            zone_status,
            f"| Network: {cvc.network_status}",
        )


        # ====================================================
        # DIAGNOSTICS + SELF-HEALING
        # ====================================================

        if (
            not args.port
            and not args.can_channel
            and cvc.zones["REAR"].status == "OFFLINE"
            and not recovery_requested
            and not recovery_completed
        ):

            print()

            # -----------------------------------------------
            # CVC DIAGNOSTICS
            # -----------------------------------------------

            faults = cvc.diagnostics()

            for fault in faults:

                print(
                    f"[DTC] {fault}"
                )


            # -----------------------------------------------
            # START SELF-HEALING
            # -----------------------------------------------

            print(
                "[SELF-HEALING] "
                "Recovery request initiated..."
            )

            cvc.request_recovery(
                "REAR"
            )

            recovery_requested = True


            # -----------------------------------------------
            # SIMULATED RECOVERY DELIVERY
            # -----------------------------------------------

            # In the physical system this command will travel:
            #
            # CVC -> ESP32 Gateway -> CAN -> Rear STM32 ECU
            #
            # The current in-memory simulator uses a shared
            # queue, so ECU-side command delivery is explicitly
            # simulated here.

            recovery_command = (
                recovery_frame(
                    "REAR"
                )
            )

            command_accepted = (
                rear_ecu.process_command(
                    recovery_command
                )
            )

            print(
                "[SELF-HEALING] "
                f"Recovery CAN ID: "
                f"0x{recovery_command.arbitration_id:03X}"
            )

            print(
                "[SELF-HEALING] "
                f"Rear ECU command accepted: "
                f"{command_accepted}"
            )

            print(
                "[SELF-HEALING] "
                "Waiting for heartbeat verification..."
            )

            print()


        # ====================================================
        # RECOVERY VERIFICATION
        # ====================================================

        if (
            recovery_requested
            and cvc.zones["REAR"].recovery_status
            == "RECOVERED"
        ):

            print()

            print(
                "[RECOVERY SUCCESS] "
                "Rear Zonal ECU heartbeat restored."
            )

            print(
                "[RECOVERY SUCCESS] "
                "Rear Zonal ECU is ONLINE."
            )

            print(
                "[RECOVERY SUCCESS] "
                "Vehicle network restored."
            )

            print(
                "[RECOVERY SUCCESS] "
                f"Recovery attempts: "
                f"{cvc.zones['REAR'].recovery_attempts}"
            )

            print()

            recovery_requested = False
            recovery_completed = True


        # ====================================================
        # LOOP DELAY
        # ====================================================

        time.sleep(1)


    # ========================================================
    # FINAL REPORT
    # ========================================================

    if not args.port and not args.can_channel:

        print()
        print("=" * 65)
        print("                    FINAL SVA STATUS")
        print("=" * 65)


        # ----------------------------------------------------
        # ZONAL ECU STATUS
        # ----------------------------------------------------

        for zone in cvc.zones:

            state = cvc.zones[
                zone
            ]

            print(
                f"{zone:<6} ECU          : "
                f"{state.status}"
            )


        # ----------------------------------------------------
        # GATEWAY + NETWORK
        # ----------------------------------------------------

        print(
            f"ESP32 Gateway      : "
            f"{cvc.gateway_status}"
        )

        print(
            f"Vehicle Network    : "
            f"{cvc.network_status}"
        )


        # ====================================================
        # FINAL DIAGNOSTICS
        # ====================================================

        print()
        print("FINAL DIAGNOSTICS")
        print("-" * 65)

        faults = cvc.diagnostics()

        if faults:

            for fault in faults:

                print(
                    f"FAULT: {fault}"
                )

        else:

            print(
                "No active faults."
            )


        # ====================================================
        # SELF-HEALING RESULT
        # ====================================================

        print()
        print("SELF-HEALING STATUS")
        print("-" * 65)

        print(
            "Rear Recovery Status   : "
            f"{cvc.zones['REAR'].recovery_status}"
        )

        print(
            "Rear Recovery Attempts : "
            f"{cvc.zones['REAR'].recovery_attempts}"
        )


        # ====================================================
        # DATA LOGGING RESULT
        # ====================================================

        print()
        print("DATA LOGGING")
        print("-" * 65)

        print(
            "Status   : COMPLETED"
        )

        print(
            f"Log File : {logger.filepath}"
        )


        # ====================================================
        # COMPLETION
        # ====================================================

        print()
        print("=" * 65)
        print(
            "        INTEGRATED SVA SIMULATION COMPLETED"
        )
        print("=" * 65)
        print()


# ============================================================
# APPLICATION ENTRY
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print()
        print("=" * 65)

        print(
            "SVA simulation stopped by user."
        )

        print(
            "Central Vehicle Computer safely terminated."
        )

        print("=" * 65)
        print()