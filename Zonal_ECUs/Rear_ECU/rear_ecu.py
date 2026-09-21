"""
REAR ZONAL ECU
Zonal Controller-Based Software Vehicle Architecture (SVA)

CAN IDs
-------
0x301 -> Rear ECU Heartbeat
0x302 -> Rear ECU Telemetry
0x310 -> Rear ECU Recovery Command

Functions
---------
- Rear obstacle monitoring
- Rear light monitoring
- Brake status monitoring
- Rear wheel/RPM monitoring
- Rear camera status monitoring
- Heartbeat transmission
- Telemetry transmission
- Fault injection
- Recovery command handling

Camera Note
-----------
The rear camera hardware is not connected in the current
software simulation stage.

Therefore:
Camera Status    -> OFFLINE
Camera Signal    -> NO SIGNAL
Camera Available -> False

The telemetry structure is already prepared so that a real
rear camera can be integrated during the hardware stage.
"""

import random
import time

from Laptop_cvc.can_protocol import (
    CANFrame,
    message_id,
    recovery_frame,
)


class RearZonalECU:
    """Software simulation of the Rear Zonal ECU."""

    def __init__(self):
        self.zone = "REAR"

        # ====================================================
        # ECU STATUS
        # ====================================================

        self.online = True
        self.fault_active = False
        self.heartbeat_count = 0

        # ====================================================
        # REAR-ZONE SENSOR DATA
        # ====================================================

        self.obstacle_distance = 100.0
        self.obstacle_status = "CLEAR"

        self.brake_status = "RELEASED"
        self.rear_light_status = "OFF"

        self.wheel_rpm = 0

        # ====================================================
        # REAR CAMERA
        # ====================================================

        # Camera hardware is not connected yet.
        # These values will later be updated using the
        # actual camera interface.

        self.camera_status = "OFFLINE"
        self.camera_signal = "NO SIGNAL"
        self.camera_location = "REAR"
        self.camera_available = False

    # ========================================================
    # SENSOR SIMULATION
    # ========================================================

    def update_sensors(self):
        """Simulate sensors connected to the Rear Zonal ECU."""

        if not self.online:
            return

        # ----------------------------------------------------
        # Rear obstacle sensor
        # ----------------------------------------------------

        self.obstacle_distance = round(
            random.uniform(5, 100),
            1,
        )

        if self.obstacle_distance < 15:
            self.obstacle_status = "WARNING"
        else:
            self.obstacle_status = "CLEAR"

        # ----------------------------------------------------
        # Brake status
        # ----------------------------------------------------

        self.brake_status = random.choice(
            [
                "RELEASED",
                "RELEASED",
                "RELEASED",
                "PRESSED",
            ]
        )

        # ----------------------------------------------------
        # Rear brake light
        # ----------------------------------------------------

        if self.brake_status == "PRESSED":
            self.rear_light_status = "ON"
        else:
            self.rear_light_status = "OFF"

        # ----------------------------------------------------
        # Rear wheel RPM
        # ----------------------------------------------------

        self.wheel_rpm = random.randint(
            300,
            1500,
        )

        # ----------------------------------------------------
        # Rear camera
        # ----------------------------------------------------

        # Do NOT simulate a fake camera connection.
        # Camera remains offline until real hardware
        # integration is implemented.

        self.camera_status = "OFFLINE"
        self.camera_signal = "NO SIGNAL"
        self.camera_location = "REAR"
        self.camera_available = False

    # ========================================================
    # HEARTBEAT - CAN ID 0x301
    # ========================================================

    def heartbeat(self):
        """Generate Rear ECU heartbeat frame."""

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
                "heartbeat_count": self.heartbeat_count,
            },
        )

    # ========================================================
    # TELEMETRY - CAN ID 0x302
    # ========================================================

    def telemetry(self):
        """Generate Rear ECU telemetry frame."""

        if not self.online:
            return None

        return CANFrame(
            arbitration_id=message_id(
                self.zone,
                "TELEMETRY",
            ),
            payload={
                "zone": self.zone,

                # Rear sensors
                "obstacle_distance": self.obstacle_distance,
                "obstacle_status": self.obstacle_status,
                "brake_status": self.brake_status,
                "rear_light_status": self.rear_light_status,
                "wheel_rpm": self.wheel_rpm,

                # Rear camera status
                "camera_status": self.camera_status,
                "camera_signal": self.camera_signal,
                "camera_location": self.camera_location,
                "camera_available": self.camera_available,

                # ECU status
                "ecu_status": "ONLINE",
            },
        )

    # ========================================================
    # COMMAND PROCESSING - CAN ID 0x310
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
        """Simulate Rear ECU communication failure."""

        self.fault_active = True
        self.online = False

    # ========================================================
    # RECOVERY
    # ========================================================

    def recover(self):
        """Recover the Rear Zonal ECU."""

        self.fault_active = False
        self.online = True

    # ========================================================
    # CAMERA STATUS
    # ========================================================

    def set_camera_status(
        self,
        available: bool,
    ):
        """
        Update rear camera connection state.

        This method prepares the Rear ECU for future
        physical camera integration.
        """

        self.camera_available = available

        if available:

            self.camera_status = "ACTIVE"
            self.camera_signal = "CONNECTED"

        else:

            self.camera_status = "OFFLINE"
            self.camera_signal = "NO SIGNAL"

    # ========================================================
    # STATUS
    # ========================================================

    def status(self):
        """Return complete Rear ECU status."""

        return {
            "zone": self.zone,
            "online": self.online,
            "fault_active": self.fault_active,
            "heartbeat_count": self.heartbeat_count,
            "camera_status": self.camera_status,
            "camera_signal": self.camera_signal,
            "camera_available": self.camera_available,
        }


# ============================================================
# REAR ECU SOFTWARE TEST
# ============================================================

def main():

    rear_ecu = RearZonalECU()

    print()
    print("=" * 60)
    print("SVA REAR ZONAL ECU - CAN PROTOCOL TEST")
    print("=" * 60)

    print()
    print("CAN CONFIGURATION")
    print("-" * 60)

    print(
        "Heartbeat CAN ID : "
        f"0x{message_id('REAR', 'HEARTBEAT'):03X}"
    )

    print(
        "Telemetry CAN ID : "
        f"0x{message_id('REAR', 'TELEMETRY'):03X}"
    )

    print(
        "Recovery CAN ID  : "
        f"0x{message_id('REAR', 'RECOVERY'):03X}"
    )

    print()
    print("REAR CAMERA CONFIGURATION")
    print("-" * 60)

    print(
        "Camera Location  : "
        f"{rear_ecu.camera_location}"
    )

    print(
        "Camera Status    : "
        f"{rear_ecu.camera_status}"
    )

    print(
        "Camera Signal    : "
        f"{rear_ecu.camera_signal}"
    )

    print(
        "Camera Available : "
        f"{rear_ecu.camera_available}"
    )

    # ========================================================
    # ECU TEST CYCLES
    # ========================================================

    for cycle in range(1, 11):

        print()
        print("-" * 60)
        print(f"ECU CYCLE {cycle}")
        print("-" * 60)

        # ----------------------------------------------------
        # Inject simulated ECU failure
        # ----------------------------------------------------

        if cycle == 6:

            print(
                "FAULT INJECTION: "
                "Rear Zonal ECU communication failure"
            )

            rear_ecu.inject_fault()

        # ----------------------------------------------------
        # Simulated CVC recovery command
        # ----------------------------------------------------

        if cycle == 8:

            print(
                "CVC -> REAR ECU: RECOVERY COMMAND"
            )

            recovery_command = recovery_frame(
                "REAR"
            )

            print(
                "Recovery CAN ID   : "
                f"0x{recovery_command.arbitration_id:03X}"
            )

            accepted = rear_ecu.process_command(
                recovery_command
            )

            print(
                "Command Accepted  :",
                accepted,
            )

        # ----------------------------------------------------
        # Normal ECU operation
        # ----------------------------------------------------

        if rear_ecu.online:

            rear_ecu.update_sensors()

            heartbeat_frame = (
                rear_ecu.heartbeat()
            )

            telemetry_frame = (
                rear_ecu.telemetry()
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
            print("REAR TELEMETRY")

            print(
                "CAN ID            : "
                f"0x{telemetry_frame.arbitration_id:03X}"
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
                "Brake Status      : "
                f"{telemetry_frame.payload['brake_status']}"
            )

            print(
                "Rear Light        : "
                f"{telemetry_frame.payload['rear_light_status']}"
            )

            print(
                "Wheel RPM         : "
                f"{telemetry_frame.payload['wheel_rpm']}"
            )

            print()
            print("REAR CAMERA")

            print(
                "Camera Status     : "
                f"{telemetry_frame.payload['camera_status']}"
            )

            print(
                "Camera Signal     : "
                f"{telemetry_frame.payload['camera_signal']}"
            )

            print(
                "Camera Location   : "
                f"{telemetry_frame.payload['camera_location']}"
            )

            print(
                "Camera Available  : "
                f"{telemetry_frame.payload['camera_available']}"
            )

            print()
            print(
                "ECU Status        : ONLINE"
            )

        else:

            print()
            print("Heartbeat         : LOST")
            print("Telemetry         : NOT AVAILABLE")
            print("Camera Data       : NOT AVAILABLE")
            print("ECU Status        : OFFLINE")

        time.sleep(1)

    # ========================================================
    # FINAL STATUS
    # ========================================================

    print()
    print("=" * 60)
    print("REAR ZONAL ECU TEST COMPLETED")
    print("=" * 60)

    final_status = rear_ecu.status()

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

    print(
        "Camera Status     : "
        f"{final_status['camera_status']}"
    )

    print(
        "Camera Signal     : "
        f"{final_status['camera_signal']}"
    )

    print(
        "Camera Available  : "
        f"{final_status['camera_available']}"
    )

    print("=" * 60)


if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print()
        print("=" * 60)
        print(
            "Rear Zonal ECU simulation "
            "stopped by user."
        )
        print("=" * 60)
    