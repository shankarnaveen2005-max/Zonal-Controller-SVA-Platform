"""
CABIN ZONAL ECU
Zonal Controller-Based Software Vehicle Architecture (SVA)

CAN IDs
-------
0x201 -> Cabin ECU Heartbeat
0x202 -> Cabin ECU Telemetry
0x210 -> Cabin ECU Recovery Command

Functions
---------
- Cabin temperature monitoring
- Driver detection
- Door status monitoring
- Seat-belt status monitoring
- Heartbeat transmission
- Telemetry transmission
- Fault injection
- Recovery command handling
"""

import random
import time

from Laptop_cvc.can_protocol import (
    CANFrame,
    message_id,
    recovery_frame,
)


# ============================================================
# CABIN ZONAL ECU
# ============================================================

class CabinZonalECU:
    """Software simulation of the Cabin Zonal ECU."""

    def __init__(self):

        self.zone = "CABIN"

        # ECU operating state
        self.online = True
        self.fault_active = False

        # Heartbeat counter
        self.heartbeat_count = 0

        # Cabin telemetry
        self.temperature = 26.0
        self.driver_detected = True

        self.door_status = {
            "front_left": "CLOSED",
            "front_right": "CLOSED",
            "rear_left": "CLOSED",
            "rear_right": "CLOSED",
        }

        self.seatbelt_status = {
            "driver": "WORN",
            "front_passenger": "WORN",
            "rear_left": "WORN",
            "rear_right": "WORN",
        }

    # ========================================================
    # SENSOR SIMULATION
    # ========================================================

    def update_sensors(self):
        """Simulate cabin sensor information."""

        if not self.online:
            return

        # Cabin temperature
        self.temperature = round(
            random.uniform(22, 32),
            1,
        )

        # Driver presence
        self.driver_detected = random.choice(
            [True, True, True, True, False]
        )

        # Door simulation
        door_names = list(
            self.door_status.keys()
        )

        for door in door_names:
            self.door_status[door] = random.choice(
                [
                    "CLOSED",
                    "CLOSED",
                    "CLOSED",
                    "CLOSED",
                    "OPEN",
                ]
            )

        # Seat-belt simulation
        belt_names = list(
            self.seatbelt_status.keys()
        )

        for belt in belt_names:
            self.seatbelt_status[belt] = random.choice(
                [
                    "WORN",
                    "WORN",
                    "WORN",
                    "WORN",
                    "NOT WORN",
                ]
            )

    # ========================================================
    # HEARTBEAT
    # CAN ID: 0x201
    # ========================================================

    def heartbeat(self):
        """Generate Cabin ECU heartbeat frame."""

        if not self.online:
            return None

        self.heartbeat_count += 1

        return CANFrame(
            arbitration_id=message_id(
                self.zone,
                "HEARTBEAT",
            ),
            payload={
                "zone": self.zone,
                "status": "ONLINE",
                "heartbeat_count":
                    self.heartbeat_count,
            },
        )

    # ========================================================
    # TELEMETRY
    # CAN ID: 0x202
    # ========================================================

    def telemetry(self):
        """Generate Cabin ECU telemetry frame."""

        if not self.online:
            return None

        return CANFrame(
            arbitration_id=message_id(
                self.zone,
                "TELEMETRY",
            ),
            payload={
                "zone": self.zone,

                "temperature":
                    self.temperature,

                "driver_detected":
                    self.driver_detected,

                "doors":
                    self.door_status.copy(),

                "seatbelts":
                    self.seatbelt_status.copy(),

                "ecu_status":
                    "ONLINE",
            },
        )

    # ========================================================
    # COMMAND PROCESSING
    # Recovery CAN ID: 0x210
    # ========================================================

    def process_command(self, frame):
        """Process commands received from the CVC."""

        expected_recovery_id = message_id(
            self.zone,
            "RECOVERY",
        )

        if frame.arbitration_id != expected_recovery_id:
            return False

        if frame.payload.get("zone") != self.zone:
            return False

        if frame.payload.get("command") != "RECOVER":
            return False

        self.recover()

        return True

    # ========================================================
    # FAULT INJECTION
    # ========================================================

    def inject_fault(self):
        """Simulate Cabin ECU communication failure."""

        self.fault_active = True
        self.online = False

    # ========================================================
    # RECOVERY
    # ========================================================

    def recover(self):
        """Recover the Cabin ECU."""

        self.fault_active = False
        self.online = True

    # ========================================================
    # STATUS
    # ========================================================

    def status(self):

        return {
            "zone": self.zone,
            "online": self.online,
            "fault_active": self.fault_active,
            "heartbeat_count":
                self.heartbeat_count,
        }


# ============================================================
# CABIN ECU SOFTWARE TEST
# ============================================================

def main():

    cabin_ecu = CabinZonalECU()

    print()
    print("=" * 60)
    print("SVA CABIN ZONAL ECU - CAN PROTOCOL TEST")
    print("=" * 60)

    print()
    print("CAN CONFIGURATION")
    print("-" * 60)

    print(
        "Heartbeat CAN ID : "
        f"0x{message_id('CABIN', 'HEARTBEAT'):03X}"
    )

    print(
        "Telemetry CAN ID : "
        f"0x{message_id('CABIN', 'TELEMETRY'):03X}"
    )

    print(
        "Recovery CAN ID  : "
        f"0x{message_id('CABIN', 'RECOVERY'):03X}"
    )

    # ========================================================
    # TEST CYCLES
    # ========================================================

    for cycle in range(1, 11):

        print()
        print("-" * 60)
        print(f"ECU CYCLE {cycle}")
        print("-" * 60)

        # ----------------------------------------------------
        # Simulated failure
        # ----------------------------------------------------

        if cycle == 6:

            print(
                "FAULT INJECTION: "
                "Cabin Zonal ECU communication failure"
            )

            cabin_ecu.inject_fault()

        # ----------------------------------------------------
        # Simulated recovery command from CVC
        # ----------------------------------------------------

        if cycle == 8:

            print(
                "CVC -> CABIN ECU: "
                "RECOVERY COMMAND"
            )

            recovery_command = recovery_frame(
                "CABIN"
            )

            print(
                "Recovery CAN ID   : "
                f"0x{recovery_command.arbitration_id:03X}"
            )

            accepted = (
                cabin_ecu.process_command(
                    recovery_command
                )
            )

            print(
                "Command Accepted  :",
                accepted,
            )

        # ----------------------------------------------------
        # Normal operation
        # ----------------------------------------------------

        if cabin_ecu.online:

            cabin_ecu.update_sensors()

            heartbeat_frame = (
                cabin_ecu.heartbeat()
            )

            telemetry_frame = (
                cabin_ecu.telemetry()
            )

            print()
            print("HEARTBEAT")

            print(
                "CAN ID            : "
                f"0x{heartbeat_frame.arbitration_id:03X}"
            )

            print(
                "Heartbeat Count   : "
                f"{heartbeat_frame.payload['heartbeat_count']}"
            )

            print()
            print("CABIN TELEMETRY")

            print(
                "CAN ID            : "
                f"0x{telemetry_frame.arbitration_id:03X}"
            )

            print(
                "Temperature       : "
                f"{telemetry_frame.payload['temperature']} °C"
            )

            driver = (
                "DETECTED"
                if telemetry_frame.payload[
                    "driver_detected"
                ]
                else "NOT DETECTED"
            )

            print(
                "Driver            : "
                f"{driver}"
            )

            print()
            print("DOOR STATUS")

            for door, status in (
                telemetry_frame.payload[
                    "doors"
                ].items()
            ):
                print(
                    f"{door:<18}: {status}"
                )

            print()
            print("SEAT-BELT STATUS")

            for seat, status in (
                telemetry_frame.payload[
                    "seatbelts"
                ].items()
            ):
                print(
                    f"{seat:<18}: {status}"
                )

            print()
            print(
                "ECU Status        : ONLINE"
            )

        # ----------------------------------------------------
        # Offline operation
        # ----------------------------------------------------

        else:

            print()
            print(
                "Heartbeat         : LOST"
            )

            print(
                "Telemetry         : NOT AVAILABLE"
            )

            print(
                "ECU Status        : OFFLINE"
            )

        time.sleep(1)

    # ========================================================
    # FINAL STATUS
    # ========================================================

    print()
    print("=" * 60)
    print("CABIN ZONAL ECU TEST COMPLETED")
    print("=" * 60)

    final_status = cabin_ecu.status()

    print(
        "Zone              : "
        f"{final_status['zone']}"
    )

    print(
        "ECU Online        : "
        f"{final_status['online']}"
    )

    print(
        "Fault Active      : "
        f"{final_status['fault_active']}"
    )

    print(
        "Heartbeat Count   : "
        f"{final_status['heartbeat_count']}"
    )

    print("=" * 60)


# ============================================================
# PROGRAM ENTRY
# ============================================================

if __name__ == "__main__":

    try:
        main()

    except KeyboardInterrupt:

        print()
        print("=" * 60)
        print(
            "Cabin Zonal ECU simulation stopped by user."
        )
        print("=" * 60)