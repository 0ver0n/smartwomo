# Installation – Truma LevelControl BLE 0.3.0 (English)

## Requirements
- Home Assistant with working Bluetooth support and a reachable Truma LevelControl device.
- A Bluetooth adapter or compatible proxy that can perform GATT reads. The original installation used the motorhome's Raspberry Pi.
- Access to `/config/custom_components/` and permission to restart Home Assistant Core safely.

## Steps
1. Back up the current Home Assistant configuration and any existing installation of `truma_levelcontrol`, including the corresponding configuration entries.
2. Copy the **complete** `custom_components/truma_levelcontrol/` folder, including Python, JSON and translation files, to `/config/custom_components/truma_levelcontrol/`. The destination folder must directly contain `manifest.json`.
3. Confirm that the copied package is version 0.3.0. Do not overwrite files from unrelated integrations.
4. Validate the configuration and restart Home Assistant Core in a controlled manner. A full Raspberry Pi reboot is not normally required.
5. Open **Settings → Devices & services → Add integration**, select “Truma LevelControl BLE”, or confirm the automatically discovered Bluetooth device.
6. If automatic discovery fails, enter **your device's own** Bluetooth address in the manual setup flow. Do not copy another user's device address.
7. Check battery, temperature, liquid height and estimated gas level entities. Polling normally occurs every 30 minutes, so allow an interval if readings are initially absent.

## Usage and troubleshooting
- The integration only reads BLE data. It does not control the heater or send undocumented commands.
- Percentage and kilogram figures are calibrated only for a **German 11 kg steel cylinder**. Other cylinder profiles have not been validated.
- For `unavailable` entities, check Bluetooth signal, adapter access, other connected applications and Home Assistant logs. Never experiment with undocumented GATT writes.
- Before upgrading, back up the working files. Only one copy of the integration should be active. To roll back, restore the original folder and restart Home Assistant Core.
- After publication, use GitHub Issues for bug reports, without posting private MAC addresses, personal logs or other sensitive data.

## Changing cylinder size / calibration

**Read the full [cylinder profile guide](CYLINDER-PROFILES.en.md) before installing a different cylinder.** It explains exactly which constants to change in `const.py`, the difference between water capacity and gas fill mass, the geometry assumptions and the optional offline calculation helper at `tools/calibrate_bottle.py`.

The default calculation is only for the previously calibrated 11 kg steel cylinder. Version 0.3.0 **does not provide a separate per-device profile selection UI**; different cylinder shapes used simultaneously need additional software support. Kilogram and percentage readings may be incorrect without the calibration described in the guide.

**Evidence for v0.3.0:** All source files were compared with the integration on the working motorhome Home Assistant Core 2026.10.1 installation. The integration is loaded and has supplied real measurements. Bluetooth connection failures can occur when the sensor battery is low: check the battery and signal before changing any production configuration. Accuracy for other cylinders remains dependent on calibration.
