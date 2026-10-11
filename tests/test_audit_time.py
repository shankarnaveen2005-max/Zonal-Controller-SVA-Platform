from Laptop_cvc.audit_time import format_audit_timestamp


def test_audit_timestamp_converts_utc_to_india_time_and_local_date() -> None:
    assert format_audit_timestamp("2026-10-10T20:00:00+00:00") == (
        "2026-10-11 01:30:00 AM IST"
    )


def test_naive_legacy_audit_timestamp_is_treated_as_utc() -> None:
    assert format_audit_timestamp("2026-10-11T00:00:00") == (
        "2026-10-11 05:30:00 AM IST"
    )
