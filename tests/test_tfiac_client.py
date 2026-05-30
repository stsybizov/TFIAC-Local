"""Standalone unit tests for the TFIAC transport layer.

These tests deliberately avoid importing ``custom_components.tfiac_local``
directly, because that package's ``__init__`` imports Home Assistant. Instead
the two Home-Assistant-free modules (``const`` and ``tfiac_client``) are loaded
into a synthetic package so their relative imports still resolve. This lets the
transport be tested with nothing but pytest installed.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import pytest

COMPONENT_DIR = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "tfiac_local"
)


def _load_client_module():
    """Load tfiac_client under a synthetic package, skipping the HA __init__."""
    pkg_name = "tfiac_standalone"
    if pkg_name not in sys.modules:
        pkg = types.ModuleType(pkg_name)
        pkg.__path__ = [str(COMPONENT_DIR)]
        sys.modules[pkg_name] = pkg

    for mod in ("const", "tfiac_client"):
        full = f"{pkg_name}.{mod}"
        if full in sys.modules:
            continue
        spec = importlib.util.spec_from_file_location(
            full, COMPONENT_DIR / f"{mod}.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[full] = module
        spec.loader.exec_module(module)

    return sys.modules[f"{pkg_name}.tfiac_client"]


tc = _load_client_module()


SAMPLE_STATUS = (
    '<msg msgid="SyncStatusReq" type="Control" seq="12345">'
    "<statusUpdateMsg>"
    "<DeviceName>Living Room</DeviceName>"
    "<TurnOn>on</TurnOn>"
    "<BaseMode>cool</BaseMode>"
    "<SetTemp>72</SetTemp>"
    "<IndoorTemp>75</IndoorTemp>"
    "<WindSpeed>Auto</WindSpeed>"
    "<WindDirection_H>on</WindDirection_H>"
    "<WindDirection_V>off</WindDirection_V>"
    "</statusUpdateMsg>"
    "</msg>"
)

ACK_OK = (
    '<msg msgid="ACKSetMessage" type="Control" seq="1">'
    "<ACKSetMessage><Return>ok</Return></ACKSetMessage></msg>"
)
ACK_FAIL = (
    '<msg msgid="ACKSetMessage" type="Control" seq="1">'
    "<ACKSetMessage><Return>fail</Return></ACKSetMessage></msg>"
)


def _make_fake_send(sent, *, status=None, ack=ACK_OK):
    """Build a fake _send that returns a status for queries and an ACK for sets."""
    status_xml = status or SAMPLE_STATUS

    async def fake_send(message, host=None):
        sent.append(message)
        if "SetMessage" in message:
            return ack.encode()
        return status_xml.encode()

    return fake_send


# --- temperature conversions -------------------------------------------------


def test_c_to_f_and_back():
    assert tc.c_to_f(0) == 32
    assert tc.c_to_f(100) == 212
    assert tc.f_to_c(32) == 0
    assert tc.f_to_c(212) == 100


def test_convert_temperature_same_unit_is_noop():
    assert tc.convert_temperature(21, "C", "c") == 21


def test_convert_temperature_cross_unit():
    assert tc.convert_temperature(25, "C", "F") == pytest.approx(77)
    assert tc.convert_temperature(77, "F", "C") == pytest.approx(25)


def test_normalize_unit_rejects_garbage():
    assert tc.normalize_unit("c") == "C"
    with pytest.raises(ValueError):
        tc.normalize_unit("kelvin")


def test_format_temperature_rounds_integers():
    assert tc._format_temperature(24.0) == "24"
    assert tc._format_temperature(24.004) == "24"
    assert tc._format_temperature(24.5) == "24.5"


# --- swing mapping -----------------------------------------------------------


@pytest.mark.parametrize(
    "mode", ["Off", "Vertical", "Horizontal", "Both"]
)
def test_swing_flag_round_trip(mode):
    h, v = tc._swing_to_flags(mode)
    assert tc._wind_flags_to_swing(h, v) == mode


# --- status parsing ----------------------------------------------------------


def test_status_from_xml_parses_fields():
    status = tc.TfiacStatus.from_xml(SAMPLE_STATUS)
    assert status.device_name == "Living Room"
    assert status.is_on is True
    assert status.base_mode == "cool"
    assert status.target_temp == 72
    assert status.current_temp == 75
    assert status.fan_mode == "Auto"
    assert status.swing_mode == "Horizontal"


def test_status_from_xml_missing_node_raises():
    with pytest.raises(ValueError):
        tc.TfiacStatus.from_xml("<msg><nope/></msg>")


def test_seq_is_seven_digits():
    client = tc.TfiacClient("192.0.2.10")
    seq = client.seq
    assert seq.isdigit()
    assert len(seq) == 7


# --- caching -----------------------------------------------------------------


def test_async_update_uses_cache_within_interval():
    client = tc.TfiacClient("192.0.2.10", min_update_interval=100)
    calls: list[str] = []

    async def fake_send(message, host=None):
        calls.append(message)
        return SAMPLE_STATUS.encode()

    client._send = fake_send  # type: ignore[assignment]

    async def scenario():
        first = await client.async_update()
        # Second call within the interval must not hit the network again.
        second = await client.async_update()
        return first, second

    first, second = asyncio.run(scenario())
    assert first is second
    assert len(calls) == 1


def test_async_update_force_bypasses_cache():
    client = tc.TfiacClient("192.0.2.10", min_update_interval=100)
    calls: list[str] = []

    async def fake_send(message, host=None):
        calls.append(message)
        return SAMPLE_STATUS.encode()

    client._send = fake_send  # type: ignore[assignment]

    asyncio.run(client.async_update())
    asyncio.run(client.async_update(force=True))
    assert len(calls) == 2


# --- set state / XML escaping ------------------------------------------------


def test_async_set_state_escapes_payload():
    client = tc.TfiacClient("192.0.2.10")
    sent: list[str] = []

    # A status whose BaseMode contains an XML-special character (decoded from
    # the &amp; entity). It must be re-escaped when echoed back in the payload.
    status_with_amp = SAMPLE_STATUS.replace(
        "<BaseMode>cool</BaseMode>", "<BaseMode>co&amp;ol</BaseMode>"
    )
    client._send = _make_fake_send(sent, status=status_with_amp)  # type: ignore[assignment]

    asyncio.run(client.async_set_state(target_temp=70, fan_mode="High"))

    set_messages = [m for m in sent if "SetMessage" in m]
    assert len(set_messages) == 1
    payload = set_messages[0]
    assert "co&amp;ol" in payload  # escaped, not raw
    assert "co&ol" not in payload.replace("co&amp;ol", "")
    assert "<SetTemp>70</SetTemp>" in payload
    assert "<WindSpeed>High</WindSpeed>" in payload


def test_async_set_state_is_optimistic_without_stale_reread():
    """After an ACK, the returned status reflects the sent values immediately.

    The device's status response lags behind a SetMessage, so async_set_state
    must not re-read it (which would return stale data). It builds an optimistic
    status from what was sent and issues exactly one status query + one set.
    """
    # Device currently reports OFF at 72; we turn it on and set 74.
    off_status = SAMPLE_STATUS.replace("<TurnOn>on</TurnOn>", "<TurnOn>off</TurnOn>")
    client = tc.TfiacClient("192.0.2.10")
    sent: list[str] = []
    client._send = _make_fake_send(sent, status=off_status)  # type: ignore[assignment]

    result = asyncio.run(
        client.async_set_state(power=True, hvac_mode="cool", target_temp=74)
    )

    assert result.is_on is True
    assert result.target_temp == 74
    assert result.base_mode == "cool"
    # One status query + one set message, no second (stale) read.
    assert len(sent) == 2
    assert sum("SetMessage" in m for m in sent) == 1


def test_async_set_state_raises_on_rejection():
    client = tc.TfiacClient("192.0.2.10")
    sent: list[str] = []
    client._send = _make_fake_send(sent, ack=ACK_FAIL)  # type: ignore[assignment]

    with pytest.raises(RuntimeError):
        asyncio.run(client.async_set_state(target_temp=70))


def test_async_turn_off_sends_off():
    client = tc.TfiacClient("192.0.2.10")
    sent: list[str] = []
    client._send = _make_fake_send(sent)  # type: ignore[assignment]

    result = asyncio.run(client.async_turn_off())
    set_messages = [m for m in sent if "SetMessage" in m]
    assert set_messages
    assert "<TurnOn>off</TurnOn>" in set_messages[0]
    assert result.is_on is False
