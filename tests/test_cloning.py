"""Unit tests for the org-prefixed key convention (§5.5 of the primitive cloning plan)."""

from envoy_pyauth.cloning import base_key, is_org_key, key_owner, org_key, org_prefix


def test_prefix_and_key():
    assert org_prefix(3) == "nc3_"
    assert org_key("fire_alarm_systems", 3) == "nc3_fire_alarm_systems"


def test_org_key_is_idempotent():
    once = org_key("fire_alarm_systems", 3)
    assert org_key(once, 3) == once


def test_rehoming_replaces_rather_than_nests():
    # A row cloned out of another org's key space must not accumulate prefixes, or the base
    # key stops round-tripping and every later dedupe compares the wrong string.
    assert org_key("nc3_fire_alarm_systems", 5) == "nc5_fire_alarm_systems"


def test_base_key_round_trip():
    assert base_key("nc3_fire_alarm_systems") == "fire_alarm_systems"
    assert base_key("fire_alarm_systems") == "fire_alarm_systems"
    assert base_key("") == ""


def test_key_owner():
    assert key_owner("nc12_pumps") == 12
    assert key_owner("pumps") is None
    # "nc" without digits is an ordinary name, not a malformed prefix.
    assert key_owner("ncpumps") is None
    assert is_org_key("nc9999_pumps", 9999) is True
    assert is_org_key("nc9999_pumps", 3) is False


def test_names_containing_the_separator_survive():
    # Underscores are ordinary characters in a key; only the leading nc<digits>_ is structural.
    assert org_key("chilled_water_pump_01", 7) == "nc7_chilled_water_pump_01"
    assert base_key("nc7_chilled_water_pump_01") == "chilled_water_pump_01"
