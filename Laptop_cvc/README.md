# Three-zone SVA platform

This prototype models a zonal-controller software vehicle architecture:

```text
STM32 Front ECU  \
STM32 Cabin ECU   -> CAN network -> ESP32 gateway -> Laptop Central Vehicle Computer
STM32 Rear ECU   /
```

## Run the simulation

From `Laptop_cvc/`:

```bash
python main.py
python digital_twin.py
```

Simulation is the default, so software development does not require hardware.
The console simulation runs for five seconds by default and keeps all three
simulated ECUs online. It does not intentionally force a Rear ECU timeout;
use the digital twin fault-injection controls or hardware heartbeat testing
when you want to verify an ECU communication fault. To change the simulation
duration:

```bash
python main.py --duration 8
```

When the ESP32 gateway is connected by USB, run the same applications in
hardware mode:

```bash
python main.py --port /dev/cu.usbserial-0001 --baud 115200
python digital_twin.py --port /dev/cu.usbserial-0001 --baud 115200
```

On Windows, use a port such as `COM5`. Install the serial dependency once with
`python -m pip install pyserial`.

The console demo runs the complete simulated three-zone network. Use the
digital twin fault-injection controls to exercise ECU, gateway, door, and
seat-belt failures.
The digital twin opens a top-view car graphic showing the Front, Cabin, and
Rear zones, CAN identifiers, four door states, four seat-belt states, live ECU
health, telemetry, diagnostics, and fault-injection controls. Green doors are
closed and green belt lines are worn; red indicates open or not worn. It
continuously renders the same
`CentralVehicleComputer` state used by the console simulation.

## CAN application protocol

The prototype uses 11-bit identifiers:

| Zone | Heartbeat | Telemetry |
| --- | ---: | ---: |
| Front | `0x101` | `0x102` |
| Cabin | `0x201` | `0x202` |
| Rear | `0x301` | `0x302` |

Frames are represented as newline-delimited JSON at the gateway boundary. This
keeps the laptop simulation deterministic while allowing the
`SerialGatewayTransport` to use the same CVC application without changing the
digital twin or diagnostics.

Each line sent or received by the ESP32 must have this shape:

```json
{"id":513,"data":{"zone":"FRONT","uptime_s":12.4}}
```

The ESP32 should translate this JSON envelope to and from native CAN frames.
STM32 nodes only need to publish the identifiers and payload fields described
by the zonal ECU contract. The laptop treats missing heartbeats as offline
after three seconds.

## Hardware integration path

1. Build each STM32 application around the `ZonalECU` message contract.
2. Add a CAN transceiver to each STM32 and the ESP32 gateway.
3. Configure all nodes for the same CAN bitrate and 120-ohm termination at the
   two physical bus ends.
4. Flash the ESP32 with a newline-delimited JSON serial bridge using the
   envelope above.
5. Run the CVC with `--port`; hardware mode stops generating simulated ECU
   frames and only consumes real CAN data.
6. Keep heartbeat timeout and diagnostics enabled during bench testing.
