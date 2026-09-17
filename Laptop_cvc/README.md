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

The console demo intentionally stops sending the rear ECU heartbeat after two
seconds, allowing the CVC heartbeat timeout and diagnostic code to be observed.
The digital twin opens a graphical vehicle model showing the Front, Cabin, and
Rear zones, CAN identifiers, live ECU health, telemetry, diagnostics, and
fault-injection controls. It continuously renders the same
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
`ESP32Gateway.send`/`receive` methods to be replaced by a real ESP32 serial or
SocketCAN transport.

## Hardware integration path

1. Build each STM32 application around the `ZonalECU` message contract.
2. Add a CAN transceiver to each STM32 and the ESP32 gateway.
3. Configure all nodes for the same CAN bitrate and 120-ohm termination at the
   two physical bus ends.
4. Replace `SimulatedCANBus` with the selected ESP32 CAN driver and transport.
5. Keep heartbeat timeout and diagnostics enabled during bench testing.
