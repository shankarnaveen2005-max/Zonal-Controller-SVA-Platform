"""Console demo for simulation or a physical ESP32 CAN gateway."""

import argparse
import time

from can_protocol import recovery_frame
from cvc_platform import CentralVehicleComputer
from data_logging import DataLogger
from esp32_gateway import (
    ESP32Gateway,
    SerialGatewayTransport,
    SimulatedGatewayTransport,
)
from zonal_ecu import ZonalECU


def main() -> None:

    # ========================================================
    # COMMAND-LINE CONFIGURATION
    # ========================================================

    parser = argparse.ArgumentParser(
        description="Run the laptop CVC"
    )

    parser.add_argument(
        "--port",
        help="ESP32 serial port"
    )

    parser.add_argument(
        "--baud",
        type=int,
        default=115200
    )

    parser.add_argument(
        "--duration",
        type=float,
        default=12.0,
        help="Simulation run time in seconds; ignored in hardware mode",
    )

    args = parser.parse_args()


    # ========================================================
    # ESP32 GATEWAY
    # ========================================================

    transport = (
        SerialGatewayTransport(args.port, args.baud)
        if args.port
        else SimulatedGatewayTransport()
    )

    gateway = ESP32Gateway(transport)


    # ========================================================
    # CENTRAL VEHICLE COMPUTER
    # ========================================================

    cvc = CentralVehicleComputer(gateway)


    # ========================================================
    # DATA LOGGER
    # ========================================================

    logger = DataLogger()


    # ========================================================
    # SIMULATED STM32 ZONAL ECUs
    # ========================================================

    ecus = (
        [
            ZonalECU("FRONT"),
            ZonalECU("CABIN"),
            ZonalECU("REAR"),
        ]
        if not args.port
        else []
    )


    # ========================================================
    # STARTUP DISPLAY
    # ========================================================

    print("\n==============================================")
    print("        THREE-ZONE SVA CVC PLATFORM")
    print("==============================================")

    print(
        "STM32 ECUs -> CAN Bus -> ESP32 Gateway "
        "-> Central Vehicle Computer"
    )

    print("Data Logging: ENABLED")

    if args.port:
        print("Operating Mode: HARDWARE")
    else:
        print("Operating Mode: SIMULATION")

    print("==============================================\n")


    # ========================================================
    # SIMULATION VARIABLES
    # ========================================================

    started = time.monotonic()

    fault_injected = False
    recovery_requested = False


    # ========================================================
    # MAIN CVC LOOP
    # ========================================================

    while (
        args.port
        or time.monotonic() - started < args.duration
    ):

        elapsed = time.monotonic() - started


        # ====================================================
        # SIMULATION MODE
        # ====================================================

        if not args.port:

            # ------------------------------------------------
            # REAR ECU FAULT INJECTION
            # ------------------------------------------------

            if elapsed >= 3 and not fault_injected:

                rear_ecu = next(
                    ecu
                    for ecu in ecus
                    if ecu.zone == "REAR"
                )

                rear_ecu.online = False

                fault_injected = True

                print(
                    "\n[FAULT INJECTION] "
                    "Rear Zonal ECU communication stopped.\n"
                )


            # ------------------------------------------------
            # GENERATE HEARTBEAT + TELEMETRY
            # ------------------------------------------------

            for ecu in ecus:

                heartbeat_frame = ecu.heartbeat(elapsed)
                telemetry_frame = ecu.telemetry(elapsed)

                for frame in (
                    heartbeat_frame,
                    telemetry_frame,
                ):

                    if frame:
                        gateway.send(frame)


        # ====================================================
        # CVC PROCESSING
        # ====================================================

        cvc.poll()


        # ====================================================
        # DATA LOGGING
        # ====================================================

        logger.log(cvc)


        # ====================================================
        # DISPLAY CURRENT NETWORK STATUS
        # ====================================================

        print(
            " | ".join(
                [
                    f"{zone}: {cvc.zones[zone].status}"
                    for zone in cvc.zones
                ]
            ),
            f"| Network: {cvc.network_status}",
        )


        # ====================================================
        # SELF-HEALING / AUTONOMOUS RECOVERY
        # ====================================================

        if (
            not args.port
            and cvc.zones["REAR"].status == "OFFLINE"
            and not recovery_requested
        ):

            print(
                "\n[DTC] "
                "DTC-CAN-301: "
                "Rear Zonal ECU communication lost"
            )

            print(
                "[SELF-HEALING] "
                "Recovery request initiated..."
            )


            # ------------------------------------------------
            # CVC CREATES RECOVERY REQUEST
            # ------------------------------------------------

            cvc.request_recovery("REAR")


            # ------------------------------------------------
            # FIND SIMULATED REAR STM32
            # ------------------------------------------------

            rear_ecu = next(
                ecu
                for ecu in ecus
                if ecu.zone == "REAR"
            )


            # ------------------------------------------------
            # SIMULATE ESP32 / CAN DELIVERY
            # ------------------------------------------------

            command = recovery_frame("REAR")

            rear_ecu.process_command(command)

            recovery_requested = True

            print(
                "[SELF-HEALING] "
                "Recovery command delivered to Rear ECU."
            )

            print(
                "[SELF-HEALING] "
                "Waiting for heartbeat verification...\n"
            )


        # ====================================================
        # RECOVERY VERIFICATION
        # ====================================================

        if (
            recovery_requested
            and cvc.zones["REAR"].recovery_status
            == "RECOVERED"
        ):

            print(
                "\n[RECOVERY SUCCESS] "
                "Rear Zonal ECU heartbeat restored."
            )

            print(
                "[RECOVERY SUCCESS] "
                "Rear Zonal ECU is ONLINE."
            )

            print(
                "[RECOVERY SUCCESS] "
                "Vehicle network restored.\n"
            )

            recovery_requested = False

            # Prevent another artificial fault injection
            fault_injected = True


        # ====================================================
        # LOOP DELAY
        # ====================================================

        time.sleep(1)


    # ========================================================
    # FINAL DIAGNOSTICS
    # ========================================================

    if not args.port:

        print("\n==============================================")
        print("              FINAL DIAGNOSTICS")
        print("==============================================")

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
        # DATA LOGGER INFORMATION
        # ====================================================

        print(
            "\nData logging completed."
        )

        print(
            f"Log file: {logger.filepath}"
        )

        print(
            "\nSimulation completed."
        )

        print(
            "==============================================\n"
        )


# ============================================================
# START APPLICATION
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print(
            "\n=============================================="
        )

        print(
            "Simulation stopped by user."
        )

        print(
            "SVA CVC safely terminated."
        )

        print(
            "==============================================\n"
        )