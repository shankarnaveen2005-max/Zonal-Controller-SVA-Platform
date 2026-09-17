import time

HEARTBEAT_TIMEOUT = 3

last_heartbeat = {
    "FRONT": time.time(),
    "CABIN": time.time(),
    "REAR": time.time()
}

ecu_status = {
    "FRONT": "ONLINE",
    "CABIN": "ONLINE",
    "REAR": "ONLINE"
}

recovery_attempted = {
    "FRONT": False,
    "CABIN": False,
    "REAR": False
}


def receive_heartbeat(zone):
    last_heartbeat[zone] = time.time()
    ecu_status[zone] = "ONLINE"


def check_ecu_health():

    current_time = time.time()

    for zone in last_heartbeat:

        if current_time - last_heartbeat[zone] > HEARTBEAT_TIMEOUT:
            ecu_status[zone] = "OFFLINE"


def self_healing():

    for zone in ecu_status:

        if ecu_status[zone] == "OFFLINE" and not recovery_attempted[zone]:

            print(f"\n⚠ Fault detected in {zone.title()} Zonal ECU")
            print(f"Recovery: Attempting {zone.title()} ECU recovery...")

            recovery_attempted[zone] = True

            # Simulated recovery action
            time.sleep(1)

            receive_heartbeat(zone)

            print(f"Recovery: {zone.title()} ECU restored ")


def display_status():

    print("\n========== ZONAL ECU HEALTH ==========")

    for zone in ["FRONT", "CABIN", "REAR"]:

        if ecu_status[zone] == "ONLINE":
            print(f"{zone.title()} Zonal ECU : ONLINE ")
        else:
            print(f"{zone.title()} Zonal ECU : OFFLINE ")

    if all(status == "ONLINE" for status in ecu_status.values()):
        print("\nOverall Vehicle Network : HEALTHY ")
    else:
        print("\nOverall Vehicle Network : FAULT DETECTED ")


print("CVC Autonomous Recovery System Started")

start_time = time.time()

while True:

    elapsed_time = time.time() - start_time

    # Front and Cabin continue working normally
    receive_heartbeat("FRONT")
    receive_heartbeat("CABIN")

    # Simulate Rear ECU failure
    if elapsed_time < 5:
        receive_heartbeat("REAR")

    check_ecu_health()

    display_status()

    self_healing()

    time.sleep(1)
