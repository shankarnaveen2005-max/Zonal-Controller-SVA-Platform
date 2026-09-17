"""CSV data logger for the SVA Central Vehicle Computer."""

import csv
import json
from datetime import datetime
from pathlib import Path

from cvc_platform import CentralVehicleComputer, ZONES


class DataLogger:
    """Record CVC status, telemetry, diagnostics and recovery data."""

    def __init__(
        self,
        filename: str = "sva_vehicle_log.csv"
    ) -> None:

        self.filepath = Path(__file__).parent / filename

        if not self.filepath.exists():

            with self.filepath.open(
                "w",
                newline="",
                encoding="utf-8"
            ) as file:

                writer = csv.writer(file)

                writer.writerow([
                    "timestamp",
                    "zone",
                    "ecu_status",
                    "network_status",
                    "gateway_status",
                    "recovery_status",
                    "recovery_attempts",
                    "telemetry",
                    "diagnostics",
                ])


    def log(
        self,
        cvc: CentralVehicleComputer
    ) -> None:

        timestamp = datetime.now().isoformat(
            timespec="seconds"
        )

        diagnostics = cvc.diagnostics()

        with self.filepath.open(
            "a",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.writer(file)

            for zone in ZONES:

                state = cvc.zones[zone]

                writer.writerow([
                    timestamp,
                    zone,
                    state.status,
                    cvc.network_status,
                    cvc.gateway_status,
                    state.recovery_status,
                    state.recovery_attempts,
                    json.dumps(state.telemetry),
                    (
                        " | ".join(diagnostics)
                        if diagnostics
                        else "NONE"
                    ),
                ])