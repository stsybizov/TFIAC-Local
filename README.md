<p align="center">
  <img src="assets/icon.png" width="128" alt="TFIAC Local icon"/>
</p>

# TFIAC Local for Home Assistant

[![hacs](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
![version](https://img.shields.io/badge/version-0.2.2-blue.svg)
![license](https://img.shields.io/badge/license-MIT-green.svg)

Local replacement for the removed Home Assistant `tfiac` integration. It talks directly to the AC over UDP port `7777`, based on the protocol used by `pytfiac`. Set up entirely from the UI (config flow), no Intelligent AC cloud account required.

## What this gives you

- Local control, no Intelligent AC cloud login required
- A custom `climate` platform you can copy into Home Assistant
- A small CLI so you can discover and test the unit before wiring it into HA

## Installation

### HACS (recommended)

1. In HACS, open the three-dot menu → **Custom repositories**.
2. Add `https://github.com/stsybizov/TFIAC-Local` with category **Integration**.
3. Install **TFIAC Local**, then restart Home Assistant.

### Manual

Copy the `custom_components/tfiac_local` folder into your HA config directory so
the final path is `/config/custom_components/tfiac_local`, then restart Home
Assistant.

## Configuration (UI)

This integration is set up from the Home Assistant UI:

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **TFIAC Local**.
3. Enter:
   - **Host / IP address** — the IP of the AC on your LAN.
   - **Name** — the entity/device name.
   - **Display temperature unit** — what Home Assistant should show (C/F).
   - **Protocol temperature unit** — what the AC expects on the wire. Start with
     `F`, because that matches the historical `pytfiac` code; if the setpoint
     behaves incorrectly, switch it to `C`.
   - **Timeout** — UDP reply timeout in seconds.

The polling interval can be changed later via the integration's **Configure**
(options) dialog.

### Migrating from YAML

Earlier versions used a `configuration.yaml` block:

```yaml
climate:
  - platform: tfiac_local
    host: 192.168.1.50
    name: Starlight AC
    temperature_unit: C
    protocol_temperature_unit: F
    timeout: 5
```

This is now **deprecated**. On startup the integration imports any such block
into a config entry automatically — after a restart you can delete the YAML.

## Discover the device

From this repo (the launcher runs the CLI without needing Home Assistant
installed):

```bash
python3 tfiac_cli.py discover
```

If broadcast discovery does not find the device, check your router DHCP lease table or the Intelligent AC app to identify the AC IP.

## Read current status

```bash
python3 tfiac_cli.py status --host 192.168.1.50
```

## Send a test command

```bash
python3 tfiac_cli.py set \
  --host 192.168.1.50 \
  --power on \
  --hvac cool \
  --temperature 24 \
  --fan Auto \
  --swing Both \
  --display-unit C \
  --protocol-unit F
```

## Behavior notes

- HVAC mode mapping:
  - `cool` -> `cool`
  - `heat` -> `heat`
  - `dry` -> `dehumi`
  - `fan_only` -> `fan`
  - `auto` -> `selfFeel`
- Power-off is handled separately from the HVAC mode.
- The protocol is local UDP/XML and does not need your Intelligent AC credentials.

## Testing

Two layers of tests live in `tests/`:

- **`test_tfiac_client.py`** — standalone unit tests for the UDP/XML transport
  (temperature conversion, status parsing, XML escaping, caching, payload
  building). They need only `pytest` and run on any Python version:

  ```bash
  pip install pytest
  python -m pytest tests/test_tfiac_client.py
  ```

- **`test_config_flow.py`, `test_init.py`, `test_climate.py`** — Home Assistant
  integration tests (config/options flow, setup/unload, entity behaviour). They
  require the HA test harness and a Python version supported by Home Assistant
  (3.12/3.13):

  ```bash
  pip install -r requirements_test.txt
  python -m pytest
  ```

  On unsupported Python versions these modules skip automatically instead of
  failing.

## Credits

This project is based on and derived from the original repository
[andreimindru96/home-assistant-tfiac-ac](https://github.com/andreimindru96/home-assistant-tfiac-ac),
which was used as the starting point for this work. It was then modernized
(config flow, update coordinator, tests, HACS packaging) and the device client
was hardened and verified against real hardware.

## Source references

- Original integration: https://github.com/andreimindru96/home-assistant-tfiac-ac
- `pytfiac`: https://github.com/fredrike/pytfiac
- Old protocol behavior inferred from `pytfiac.py`

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

[MIT](LICENSE) © 2026 audel
