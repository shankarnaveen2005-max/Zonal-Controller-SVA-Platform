"""
FRONT ZONAL ECU
Zonal Controller-Based Software Vehicle Architecture (SVA)

Software simulation of the Front Zonal Controller.

CAN IDs
-------
0x101 -> Front ECU Heartbeat
0x102 -> Front ECU Telemetry
0x110 -> Front ECU Recovery Command

Functions
---------
- Vehicle speed simulation
- Steering angle simulation
- Front obstacle monitoring
- Heartbeat transmission
- Telemetry transmission
- Fault injection
- Recovery command reception
- ECU recovery
"""

import random
import time

from Laptop_cvc.can_protocol import (
    CANFrame,
    message_id,
    recovery_frame,
)
from Laptop_cvc.esp32_gateway import (
    ESP32Gateway,
    SimulatedGatewayTransport,
)


# ============================================================
# FRONT ZONAL ECU
# ============================================================

class FrontZonalECU:
    """Software simulation of the Front Zonal ECU."""

    def __init__(self):

        self.zone = "FRONT"

        # ECU operating state
        self.online = True
        self.fault_active = False

        # Heartbeat counter
        self.heartbeat_count = 0

        # Front-zone telemetry
        self.speed = 0.0
        self.steering_angle = 0.0
        self.obstacle_distance = 100.0
        self.obstacle_status = "CLEAR"

    # ========================================================
    # SENSOR SIMULATION
    # ========================================================

    def update_sensors(self):
        """
        Simulates the sensors connected to the
        Front Zonal ECU.
        """

        if not self.online:
            return

        # Simulated vehicle speed
        self.speed = round(
            random.uniform(20, 80),
            1,
        )

        # Simulated steering angle
        self.steering_angle = round(
            random.uniform(-30, 30),
            1,
        )

        # Simulated front obstacle distance
        self.obstacle_distance = round(
            random.uniform(5, 100),
            1,
        )

        # Determine obstacle condition
        if self.obstacle_distance < 15:
            self.obstacle_status = "WARNING"
        else:
            self.obstacle_status = "CLEAR"

    # ========================================================
    # HEARTBEAT MESSAGE
    # CAN ID: 0x101
    # ========================================================

    def heartbeat(self):
        """
        Generates the Front ECU heartbeat CAN frame.
        """

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
    # TELEMETRY MESSAGE
    # CAN ID: 0x102
    # ========================================================

    def telemetry(self):
        """
        Generates the Front ECU telemetry CAN frame.
        """

        if not self.online:
            return None

        return CANFrame(
            arbitration_id=message_id(
                self.zone,
                "TELEMETRY",
            ),
            payload={
                "zone": self.zone,

                "speed":
                    self.speed,

                "steering_angle":
                    self.steering_angle,

                "obstacle_distance":
                    self.obstacle_distance,

                "obstacle_status":
                    self.obstacle_status,

                "ecu_status":
                    "ONLINE",
            },
        )

    # ========================================================
    # COMMAND PROCESSING
    # ========================================================

    def process_command(self, frame):
        """
        Processes commands received from the CVC.

        Currently supported:
        RECOVER command using CAN ID 0x110.
        """

        expected_recovery_id = message_id(
            self.zone,
            "RECOVERY",
        )

        # Check CAN ID
        if frame.arbitration_id != expected_recovery_id:
            return False

        # Check target zone
        if frame.payload.get("zone") != self.zone:
            return False

        # Check recovery command
        if frame.payload.get("command") != "RECOVER":
            return False

        self.recover()

        return True

    # ========================================================
    # FAULT INJECTION
    # ========================================================

    def inject_fault(self):
        """
        Simulates a Front Zonal ECU communication failure.
        """

        self.fault_active = True
        self.online = False

    # ========================================================
    # RECOVERY
    # ========================================================

    def recover(self):
        """
        Restores the Front Zonal ECU after receiving
        a valid recovery command from the CVC.
        """

        self.fault_active = False
        self.online = True

    # ========================================================
    # STATUS
    # ========================================================

    def status(self):
        """
        Returns the current Front ECU status.
        """

        return {
            "zone": self.zone,
            "online": self.online,
            "fault_active": self.fault_active,
            "heartbeat_count":
                self.heartbeat_count,
        }

    def transmit(self, gateway):
        """Send the current heartbeat and telemetry over the CAN gateway."""

        if not self.online:
            return []

        self.update_sensors()
        frames = [self.heartbeat(), self.telemetry()]

        for frame in frames:
            gateway.send(frame)

        return frames


# ============================================================
# FRONT ECU SOFTWARE TEST
# ============================================================

def main():

    front_ecu = FrontZonalECU()
    gateway = ESP32Gateway(SimulatedGatewayTransport())

    print()
    print("=" * 60)
    print("SVA FRONT ZONAL ECU - CAN PROTOCOL TEST")
    print("=" * 60)

    print()
    print("CAN CONFIGURATION")
    print("-" * 60)

    print(
        "Heartbeat CAN ID : "
        f"0x{message_id('FRONT', 'HEARTBEAT'):03X}"
    )

    print(
        "Telemetry CAN ID : "
        f"0x{message_id('FRONT', 'TELEMETRY'):03X}"
    )

    print(
        "Recovery CAN ID  : "
        f"0x{message_id('FRONT', 'RECOVERY'):03X}"
    )

    # --------------------------------------------------------
    # ECU TEST CYCLES
    # --------------------------------------------------------

    for cycle in range(1, 11):

        print()
        print("-" * 60)
        print(f"ECU CYCLE {cycle}")
        print("-" * 60)

        # ----------------------------------------------------
        # SIMULATE FRONT ECU FAILURE
        # ----------------------------------------------------

        if cycle == 6:

            print(
                "FAULT INJECTION:"
                " Front Zonal ECU communication failure"
            )

            front_ecu.inject_fault()

        # ----------------------------------------------------
        # SIMULATE CVC RECOVERY COMMAND
        # ----------------------------------------------------

        if cycle == 8:

            print(
                "CVC -> FRONT ECU:"
                " RECOVERY COMMAND"
            )

            recovery_command = recovery_frame(
                "FRONT"
            )

            print(
                "Recovery CAN ID   : "
                f"0x{recovery_command.arbitration_id:03X}"
            )

            gateway.send(recovery_command)

            accepted = False

            for frame in gateway.receive():
                accepted = front_ecu.process_command(frame) or accepted

            print(
                "Command Accepted  :",
                accepted,
            )

        # ----------------------------------------------------
        # NORMAL ECU OPERATION
        # ----------------------------------------------------

        if front_ecu.online:

            transmitted_frames = front_ecu.transmit(gateway)
            heartbeat_frame, telemetry_frame = transmitted_frames

            print()
            print("CAN BUS OUTPUT")
            for frame in gateway.receive():
                print(
                    f"TX CAN 0x{frame.arbitration_id:03X}: "
                    f"{frame.to_wire()}"
                )

            # ------------------------------------------------
            # HEARTBEAT OUTPUT
            # ------------------------------------------------

            print()
            print("HEARTBEAT")

            print(
                "CAN ID            : "
                f"0x{heartbeat_frame.arbitration_id:03X}"
            )

            print(
                "Zone              : "
                f"{heartbeat_frame.payload['zone']}"
            )

            print(
                "Heartbeat Count   : "
                f"{heartbeat_frame.payload['heartbeat_count']}"
            )

            # ------------------------------------------------
            # TELEMETRY OUTPUT
            # ------------------------------------------------

            print()
            print("FRONT TELEMETRY")

            print(
                "CAN ID            : "
                f"0x{telemetry_frame.arbitration_id:03X}"
            )

            print(
                "Vehicle Speed     : "
                f"{telemetry_frame.payload['speed']} km/h"
            )

            print(
                "Steering Angle    : "
                f"{telemetry_frame.payload['steering_angle']} deg"
            )

            print(
                "Obstacle Distance : "
                f"{telemetry_frame.payload['obstacle_distance']} m"
            )

            print(
                "Obstacle Status   : "
                f"{telemetry_frame.payload['obstacle_status']}"
            )

            print(
                "ECU Status        : ONLINE"
            )

        # ----------------------------------------------------
        # OFFLINE ECU
        # ----------------------------------------------------

        else:

            print()
            print("Heartbeat         : LOST")
            print("Telemetry         : NOT AVAILABLE")
            print("ECU Status        : OFFLINE")

        time.sleep(1)

    # --------------------------------------------------------
    # FINAL STATUS
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("FRONT ZONAL ECU TEST COMPLETED")
    print("=" * 60)

    final_status = front_ecu.status()

    print(
        f"Zone              : "
        f"{final_status['zone']}"
    )

    print(
        f"ECU Online        : "
        f"{final_status['online']}"
    )

    print(
        f"Fault Active      : "
        f"{final_status['fault_active']}"
    )

    print(
        f"Heartbeat Count   : "
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
        print("Front Zonal ECU simulation stopped by user.")
        print("=" * 60)