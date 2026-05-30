"""Shared pytest configuration.

The Home-Assistant-based tests need ``pytest-homeassistant-custom-component``.
When that plugin is not installed (e.g. running only the standalone transport
tests on an unsupported Python version), we degrade gracefully so the rest of
the suite still runs.
"""

import pytest

try:
    import pytest_homeassistant_custom_component  # noqa: F401

    pytest_plugins = ["pytest_homeassistant_custom_component"]
    _HAS_HA = True
except ImportError:  # pragma: no cover - depends on the environment
    _HAS_HA = False


if _HAS_HA:

    @pytest.fixture(autouse=True)
    def auto_enable_custom_integrations(enable_custom_integrations):
        """Enable loading the custom integration in every HA test."""
        yield

    @pytest.fixture
    def make_status():
        """Return a factory that builds TfiacStatus objects for tests."""
        from custom_components.tfiac_local.tfiac_client import TfiacStatus

        def _make(
            *,
            name: str = "Living Room",
            is_on: bool = True,
            base_mode: str = "cool",
            target_temp: float = 72.0,
            current_temp: float | None = 75.0,
            fan_mode: str = "Auto",
            swing_mode: str = "Off",
        ) -> TfiacStatus:
            return TfiacStatus(
                device_name=name,
                is_on=is_on,
                base_mode=base_mode,
                target_temp=target_temp,
                current_temp=current_temp,
                fan_mode=fan_mode,
                swing_mode=swing_mode,
                raw={
                    "DeviceName": name,
                    "TurnOn": "on" if is_on else "off",
                    "BaseMode": base_mode,
                    "SetTemp": str(int(target_temp)),
                    "IndoorTemp": "" if current_temp is None else str(int(current_temp)),
                    "WindSpeed": fan_mode,
                    "WindDirection_H": "off",
                    "WindDirection_V": "off",
                },
            )

        return _make
