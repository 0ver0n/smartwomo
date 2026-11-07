# Truma LevelControl BLE – independent Home Assistant integration

**Version:** 0.3.0 · **Original developer / project initiator:** Marcel Lörz (GitHub: 0ver0n) · https://www.blindmitwomo.com · **License:** Apache-2.0.

This independent Home Assistant integration reads a Truma LevelControl cylinder sensor through Home Assistant's local Bluetooth adapter. It does not require the Truma cloud or an iNet Box. It is neither official nor certified by Truma.

## Features

- Automatic Bluetooth discovery or manual configuration of the device's own Bluetooth address.
- Multiple sensors supported. **In v0.3.0 all configured sensors share a single global cylinder geometry profile.**
- Battery status, Bluetooth signal, temperature, ultrasonic transit time, liquid height and estimated gas mass (kg) and fill percentage.
- Diagnostic values, optional raw sensor bytes and rejection of implausible ultrasound reflections. No BLE write commands.
- Polling every 30 minutes, including a settling period for reliable GATT reads.

## Before using the fill-level figures

The default calibration is **specific to one German 11 kg steel cylinder** (a 289 mm sensor reading corresponded to 84% or 9.2 kg in the official app on September 15, 2026). Other 5, 11 or 33 kg cylinders may have different diameters and rounded ends. Their fill level cannot be assumed accurate without recalibration.

**[Full adaptation instructions with every constant and an offline calculation tool](CYLINDER-PROFILES.en.md).** Changing bottle size in the manufacturer's app does NOT change our integration. Verify customized `const.py` values with at least two manufacturer-app readings at different fill levels. Profiles for differently shaped cylinders used simultaneously require a future per-device feature.

This is a convenience indication, **not a gas leak, pressure or safety monitor**. If measurements become stale, check the sensor batteries and Bluetooth signal before editing software. The manufacturer specifies two AAA batteries.

## Installation and compatibility

[Full installation/user guide (English)](INSTALLATION.en.md) · [German guide](INSTALLATION.de.md).

Copy only `custom_components/truma_levelcontrol/` to the equivalent folder under Home Assistant `/config/custom_components/`. The optional `tools/calibrate_bottle.py` runs offline on your own computer.

**Live evidence:** All eight source files are byte-identical with the installed integration on the motorhome running Home Assistant Core 2026.10.1. Its configuration entry is loaded and live BLE readings have been observed. This does not establish compatibility with all future HA versions or cylinder geometries.

**License and origin:** [Apache License 2.0](LICENSE) and [NOTICE](NOTICE). Independent of and not endorsed by Truma. No device-specific address or password is included in the source package.
