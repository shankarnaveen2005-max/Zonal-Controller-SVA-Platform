"""OTA firmware update manager for the SVA platform."""

from dataclasses import dataclass
import time


@dataclass
class OTAResult:
    zone: str
    old_version: str
    new_version: str
    status: str
    progress: int
    message: str


class OTAManager:
    """Manages simulated OTA firmware updates for zonal ECUs."""

    def __init__(self) -> None:

        self.firmware_versions = {
            "FRONT": "v1.0.0",
            "CABIN": "v1.0.0",
            "REAR": "v1.0.0",
        }

        self.update_status = {
            "FRONT": "IDLE",
            "CABIN": "IDLE",
            "REAR": "IDLE",
        }

        self.progress = {
            "FRONT": 0,
            "CABIN": 0,
            "REAR": 0,
        }

    def _validate_zone(
        self,
        zone: str,
    ) -> None:

        if zone not in self.firmware_versions:
            raise ValueError(
                f"Unknown zonal ECU: {zone}"
            )

    def get_version(
        self,
        zone: str,
    ) -> str:

        self._validate_zone(zone)

        return self.firmware_versions[zone]

    def check_update(
        self,
        zone: str,
        new_version: str,
    ) -> bool:

        self._validate_zone(zone)

        return (
            self.firmware_versions[zone]
            != new_version
        )

    def update(
        self,
        zone: str,
        new_version: str,
    ) -> OTAResult:

        self._validate_zone(zone)

        old_version = (
            self.firmware_versions[zone]
        )

        if old_version == new_version:

            return OTAResult(
                zone=zone,
                old_version=old_version,
                new_version=new_version,
                status="UP TO DATE",
                progress=100,
                message="Firmware already up to date.",
            )

        self.update_status[zone] = "DOWNLOADING"

        for progress in range(
            0,
            101,
            20,
        ):

            self.progress[zone] = progress
            time.sleep(0.05)

        self.update_status[zone] = "VERIFYING"
        time.sleep(0.1)

        self.update_status[zone] = "INSTALLING"
        time.sleep(0.1)

        self.update_status[zone] = "RESTARTING"
        time.sleep(0.1)

        self.firmware_versions[zone] = (
            new_version
        )

        self.progress[zone] = 100
        self.update_status[zone] = "COMPLETED"

        return OTAResult(
            zone=zone,
            old_version=old_version,
            new_version=new_version,
            status="COMPLETED",
            progress=100,
            message=(
                f"{zone} Zonal ECU firmware "
                f"updated successfully."
            ),
        )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    ota = OTAManager()

    print("\nSVA OTA UPDATE FRAMEWORK")
    print("=" * 40)

    for zone in (
        "FRONT",
        "CABIN",
        "REAR",
    ):
        print(
            f"{zone}: "
            f"{ota.get_version(zone)}"
        )

    print("\nUpdating FRONT ECU...")

    result = ota.update(
        "FRONT",
        "v1.1.0",
    )

    print(
        f"Old Version : {result.old_version}"
    )

    print(
        f"New Version : {result.new_version}"
    )

    print(
        f"Status      : {result.status}"
    )

    print(
        f"Progress    : {result.progress}%"
    )

    print(
        f"Message     : {result.message}"
    )