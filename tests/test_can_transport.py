from Laptop_cvc.can_protocol import CANFrame
from Laptop_cvc.esp32_gateway import decode_payload, encode_payload


def test_encode_decode_payload_round_trip() -> None:
    frame = CANFrame(
        arbitration_id=0x101,
        payload={"zone": "FRONT", "uptime_s": 12.4},
    )

    encoded = encode_payload(frame.payload)
    decoded = decode_payload(encoded)

    assert decoded == frame.payload
