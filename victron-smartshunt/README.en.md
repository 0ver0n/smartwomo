# Victron SmartShunt – Home Assistant VE.Direct / MQTT add-on

**Version:** 4.2.3 · **Project initiator:** Marcel Lörz (0ver0n), https://www.blindmitwomo.com · **License:** Apache-2.0.

This independent free Home Assistant app connects to a Victron SmartShunt through a USB VE.Direct cable and publishes readings to an MQTT broker. Sensors and controls can be discovered via Home Assistant MQTT Discovery.

## Features
- Battery voltage, current, state of charge, power, discharge history, alarm state, and other available VE.Direct readings.
- Optional raw debug events and periodic summary data.
- Robust parser handling for separate live/history frames and serial or MQTT reconnection.
- **Optional** reading and writing of selected VE.Direct HEX registers through MQTT. This is **DISABLED by default**; enabling write commands can change important battery-monitor parameters.

## Security in 4.2.3
- AppArmor enabled; `SYS_RAWIO` removed; **no writeable Home Assistant configuration mount**.
- Serial access through the add-on's `uart: true` and `udev: true` options.
- Persistent file logs restricted to private `/data`; old settings referring to `/config` fall back safely to `/data`.
- `publish_raw=false` and `hex_enabled=false` by default.
- MQTT credentials must be configured in the app settings, never committed to this project.
- MQTT-based HEX write controls require deliberately enabling HEX support and securing the broker against untrusted publishers.

## Requirements and compatibility
Validated source base: Victron SmartShunt 300 A over USB VE.Direct on the author's motorhome. The original 4.2.2 is running with Home Assistant Core 2026.10.1 and publishing real telemetry. Version 4.2.3 tightens privileges and modifies defaults: test it in your own environment before replacing a working installation. No claim of certification for other firmware or models.

**Guides:** [English installation](INSTALLATION.en.md) · [Deutsch](INSTALLATION.de.md). [QA report](QA-REPORT.md). [Changelog](CHANGELOG.md).

Independent community software, not an official Victron Energy product. Incorrect SOC or changed monitor settings can affect charging and safety; do not rely on this software as the sole protective system.
