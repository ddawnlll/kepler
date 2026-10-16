"""Known-answer tests for the H6 vintage-aware as-of contract."""
from datetime import date, datetime, timedelta, timezone

from kepler.intelligence.vintages import MacroVintage, asof_macro_vintages

UTC = timezone.utc


def at(day, hour=0, minute=0):
    return datetime(2025, 1, day, hour, minute, tzinfo=UTC)


def release(value, *, period=date(2024, 12, 31), vintage_id="v1", publication=at(5),
            vintage=at(5), available=at(5), unit="percent", source="fixture", source_sha256="a" * 64):
    return MacroVintage("credit_spread", period, value, unit, source, source_sha256,
                        vintage_id, publication, vintage, available)


def test_release_is_hidden_until_actual_availability_including_publication_delay():
    first = release(2.5, publication=at(5), vintage=at(5), available=at(7, 12))
    assert asof_macro_vintages([first], at(7, 11, 59)) == ()
    assert asof_macro_vintages([first], at(7, 12)) == (first,)
    assert asof_macro_vintages([first], at(7, 12) + timedelta(microseconds=1)) == (first,)


def test_revision_replaces_first_release_only_after_revision_is_available():
    first = release(2.5, vintage_id="2025-01-05", publication=at(5), vintage=at(5), available=at(5))
    revised = release(3.1, vintage_id="2025-02-03", publication=at(8), vintage=at(8),
                      available=at(8), period=first.observation_period_end)
    assert asof_macro_vintages([revised, first], at(7)) == (first,)
    assert asof_macro_vintages([first, revised], at(8)) == (revised,)


def test_late_ingested_old_vintage_cannot_overwrite_newer_visible_revision():
    old = release(2.5, vintage_id="old", publication=at(5), vintage=at(5), available=at(10))
    revised = release(3.1, vintage_id="new", publication=at(6), vintage=at(6), available=at(6))

    assert asof_macro_vintages([old, revised], at(9)) == (revised,)
    assert asof_macro_vintages([revised, old], at(11)) == (revised,)


def test_future_release_perturbation_and_input_order_do_not_change_past_asof_view():
    old = release(2.5, vintage_id="v1", available=at(5))
    second_period = release(1.8, period=date(2025, 1, 31), vintage_id="v1",
                            publication=at(8), vintage=at(8), available=at(8))
    future_revision = release(9000.0, vintage_id="future", publication=at(8), vintage=at(8),
                              available=at(8), period=old.observation_period_end)
    expected = asof_macro_vintages([old], at(7))
    assert asof_macro_vintages([future_revision, second_period, old], at(7)) == expected
    assert asof_macro_vintages([old, second_period, future_revision], at(7)) == expected


def test_visible_series_unit_change_fails_closed_but_future_unit_is_irrelevant():
    old = release(2.5, available=at(5))
    future = release(250.0, vintage_id="future", available=at(8), unit="basis_points",
                     publication=at(8), vintage=at(8), period=old.observation_period_end)
    assert asof_macro_vintages([old, future], at(7)) == (old,)
    changed = release(250.0, vintage_id="visible-change", available=at(8), unit="basis_points",
                      publication=at(8), vintage=at(8), period=date(2025, 1, 31))
    try:
        asof_macro_vintages([old, changed], at(8))
    except ValueError as error:
        assert "inconsistent units" in str(error)
    else:
        raise AssertionError("visible unit changes must fail closed")


def test_conflicting_same_time_vintages_are_rejected():
    a = release(2.5, vintage_id="same", available=at(5))
    b = release(2.6, vintage_id="same", available=at(5))
    try:
        asof_macro_vintages([a, b], at(5))
    except ValueError as error:
        assert "ambiguous" in str(error)
    else:
        raise AssertionError("conflicting vintage duplicates must fail closed")


def test_unreleased_observation_is_absent_not_forward_filled_or_zero_filled():
    future = release(0.0, publication=at(9), vintage=at(9), available=at(9))
    result = asof_macro_vintages([future], at(8, 23, 59))
    assert result == ()


def test_macro_contract_rejects_naive_or_inconsistent_source_timestamps():
    try:
        release(1.0, publication=datetime(2025, 1, 5), vintage=at(5), available=at(5))
    except ValueError as error:
        assert "timezone-aware" in str(error)
    else:
        raise AssertionError("naive publication time must be rejected")
    try:
        release(1.0, publication=at(6), vintage=at(5), available=at(6))
    except ValueError as error:
        assert "precede publication" in str(error)
    else:
        raise AssertionError("vintage time before publication must be rejected")
    try:
        release(1.0, source_sha256="unhashed")
    except ValueError as error:
        assert "SHA256" in str(error)
    else:
        raise AssertionError("unhashed macro source record must be rejected")

